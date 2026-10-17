"""Linear issue activity collector (second ingestion source).

Reads users.txt (same file github.py uses; Linear keys people by email,
non-email lines are matched against real/display names), pulls every
issue touched today (GraphQL filter on updatedAt) with its comments,
and maps each user to what they did:

    {
        "<user>": {
            "username": "<user>",
            "teams": {"<team>": {"issues": [{..., "comments": [...]}]}}
        }
    }

An issue is attributed to a user if they created it, are assigned to it,
or wrote a comment on it today.
"""

import os
import time
from datetime import datetime, timezone

import requests

API_URL = "https://api.linear.app/graphql"

QUERY = """
query Issues($filter: IssueFilter!, $after: String) {
  issues(first: 50, after: $after, filter: $filter, orderBy: updatedAt) {
    nodes {
      identifier
      title
      description
      state { name }
      assignee { email name displayName }
      creator { email name displayName }
      createdAt
      updatedAt
      team { name }
      labels { nodes { name } }
      comments {
        nodes {
          body
          createdAt
          user { email name displayName }
        }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""


class LinearError(RuntimeError):
    pass


_session = requests.Session()


def _request(query, variables):
    token = os.getenv("LINEAR_TOKEN")
    if not token:
        raise LinearError("LINEAR_TOKEN is not set (linear/.env or environment).")
    last_exc = None
    for attempt in range(3):  # transient network failures, mirroring github.py
        try:
            resp = _session.post(
                API_URL,
                json={"query": query, "variables": variables},
                headers={"Authorization": token},
                timeout=30,
            )
            resp.raise_for_status()
        except requests.HTTPError as exc:  # real API error (401/403/429...): no point retrying
            last_exc = exc
            break
        except requests.RequestException as exc:  # connection drops, timeouts
            last_exc = exc
            time.sleep(1 * (attempt + 1))
            continue
        data = resp.json()
        if data.get("errors"):
            raise LinearError(f"Linear GraphQL errors: {data['errors']}")
        return data["data"]
    raise LinearError(f"Linear request failed: {last_exc}")


def todays_comments(comments, day):
    """Keep only comments written on `day` (UTC)."""
    kept = []
    for c in comments:
        user = c.get("user") or {}
        if c.get("createdAt", "")[:10] != day.isoformat():
            continue
        kept.append({
            "body": c.get("body"),
            "author_email": user.get("email"),
            "author_name": user.get("displayName") or user.get("name"),
            "date": c.get("createdAt"),
        })
    return kept


def _person_names(person):
    """All identifier strings a Linear user can be matched by."""
    if not person:
        return set()
    found = set()
    for value in (person.get("email"), person.get("displayName"), person.get("name")):
        if value:
            found.add(value.lower())
    return found


def user_participates(user, issue_record):
    """User touched this issue if they created it, are assigned to it,
    or commented on it today. Works on the slim record from issue_record()."""
    u = user.lower()
    if u in _person_names({"email": issue_record.get("assignee_email"), "name": issue_record.get("assignee_name")}):
        return True
    if issue_record.get("creator_email") and issue_record["creator_email"].lower() == u:
        return True
    for c in issue_record["comments"]:
        if u in _person_names({"email": c["author_email"], "name": c["author_name"]}):
            return True
    return False


def issue_record(node, day):
    """Slimmed-down issue dict with only today's comments."""
    comments = (node.get("comments") or {}).get("nodes", [])
    today_comments = todays_comments(comments, day)
    return {
        "identifier": node["identifier"],
        "title": node["title"],
        "description": node.get("description"),
        "state": (node.get("state") or {}).get("name"),
        "assignee_email": (node.get("assignee") or {}).get("email"),
        "assignee_name": (node.get("assignee") or {}).get("displayName") or (node.get("assignee") or {}).get("name"),
        "creator_email": (node.get("creator") or {}).get("email"),
        "labels": [l["name"] for l in (node.get("labels") or {}).get("nodes", [])],
        "created_at": node["createdAt"],
        "updated_at": node["updatedAt"],
        "comments": today_comments,
    }


def issues_touched_today(day):
    """All issues updated on `day` (UTC), across every team, following cursors."""
    start = f"{day.isoformat()}T00:00:00Z"
    issues = []
    after = None
    while True:
        data = _request(QUERY, {
            "filter": {"updatedAt": {"gte": start}},
            "after": after,
        })
        conn = data["issues"]
        issues.extend(conn["nodes"])
        if not conn["pageInfo"]["hasNextPage"]:
            return issues
        after = conn["pageInfo"]["endCursor"]


def collect_activity(users_file, day=None):
    """Map every user in users_file to their Linear issue work today."""
    day = day or datetime.now(timezone.utc).date()
    from github import read_lines  # same users.txt format as the GitHub ingestion
    users = read_lines(users_file)
    activity = {u.lower(): {"username": u, "teams": {}} for u in users}

    for node in issues_touched_today(day):
        issue = issue_record(node, day)
        team = (node.get("team") or {}).get("name") or "unknown"
        for user, entry in activity.items():
            if user_participates(user, issue):
                entry["teams"].setdefault(team, {"issues": []})["issues"].append(issue)

    for entry in activity.values():
        for team_data in entry["teams"].values():
            team_data["issues"].sort(key=lambda i: i["identifier"])
    return activity


if __name__ == "__main__":
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv()
    here = Path(__file__).resolve().parent
    import json
    print(json.dumps(collect_activity(here / "users.txt"), indent=2))
