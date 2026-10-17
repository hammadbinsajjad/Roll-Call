"""GitHub PR activity collector.

Reads repos.txt (one "owner/repo" per line) and users.txt (one GitHub
username or email per line), pulls every PR touched today on each repo
with its details and commits, and maps each user to what they did:

    {
        "octocat": {
            "username": "octocat",
            "repos": {
                "owner/repo": {"pull_requests": [{..., "commits": [...]}]}
            }
        }
    }
"""

import json
import os
import re
import time
from datetime import date, datetime, timezone

import requests

BASE_URL = "https://api.github.com"
USER_AGENT = "roll-call-ingestion/0.1 (supperhammad2002@gmail.com)"  # GitHub asks every client to send a meaningful User-Agent


class GitHubError(RuntimeError):
    pass


_session = requests.Session()  # one session reuses connections across all pages


def _request(path, params=None):
    url = BASE_URL + path
    headers = {"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    last_exc = None
    for attempt in range(3):  # transient network errors (dropped/truncated responses) are common
        try:
            resp = _session.get(url, params=params, headers=headers, timeout=30)
            resp.raise_for_status()  # real API error (401/403/422...): no point retrying
            return resp.json(), resp.headers
        except requests.HTTPError as exc:
            last_exc = exc
            break
        except requests.RequestException as exc:  # connection drops, truncated reads, timeouts
            last_exc = exc
            time.sleep(1 * (attempt + 1))
    raise GitHubError(
        f"GitHub request failed: {url} ({last_exc}). "
        "Set GITHUB_TOKEN to avoid unauthenticated rate limits."
    ) from last_exc


def _paged(path, params=None):
    """Yield all pages of a list endpoint, following the Link header."""
    params = dict(params or {}, per_page=100)
    while True:
        data, headers = _request(path, params)
        yield from data
        link = headers.get("Link", "")
        m = re.search(r'<([^>]+)>;\s*rel="next"', link)
        if not m:
            return
        # next URL is absolute; convert back to a path + params
        next_url = m.group(1)
        path, _, query = next_url[len(BASE_URL):].partition("?")
        params = dict(pair.split("=", 1) for pair in query.split("&"))


def read_lines(path):
    lines = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                lines.append(line)
    return lines


def _is_today(iso_ts, day):
    """GitHub timestamps are ISO 8601 in UTC; 'today' means the UTC day."""
    return iso_ts[:10] == day.isoformat()


def todays_commits(commits, day):
    """Keep only commits authored on `day` (UTC)."""
    kept = []
    for c in commits:
        author = c.get("commit", {}).get("author", {})
        if not _is_today(author.get("date", ""), day):
            continue
        kept.append({
            "sha": c["sha"],
            "message": c["commit"].get("message"),
            "author_login": (c.get("author") or {}).get("login"),
            "author_name": author.get("name"),
            "author_email": author.get("email"),
            "date": author.get("date"),
        })
    return kept


def _commit_identifiers(commits):
    """All (login, email) pairs that appear as commit authors."""
    found = set()
    for c in commits:
        # accepts both raw GitHub commits and the slim records from todays_commits()
        login = (c.get("author") or {}).get("login") or c.get("author_login")
        email = c.get("commit", {}).get("author", {}).get("email") or c.get("author_email")
        if login:
            found.add(login.lower())
        if email:
            found.add(email.lower())
    return found


def user_participates(user, pr_details, pr_commits):
    """User touched this PR if they authored it, authored a commit today,
    or were requested as reviewer / assigned."""
    u = user.lower()
    if (pr_details.get("user") or {}).get("login", "").lower() == u:
        return True
    if u in _commit_identifiers(pr_commits):
        return True
    reviewers = {r.get("login", "").lower() for r in pr_details.get("requested_reviewers", [])}
    assignees = {r.get("login", "").lower() for r in pr_details.get("assignees", [])}
    return u in reviewers or u in assignees


def pr_record(details, commits, day):
    """Slimmed-down PR dict with only today's commits."""
    return {
        "number": details["number"],
        "title": details["title"],
        "state": details["state"],
        "merged": details.get("merged", False),
        "draft": details.get("draft", False),
        "html_url": details["html_url"],
        "author": (details.get("user") or {}).get("login"),
        "created_at": details["created_at"],
        "updated_at": details["updated_at"],
        "requested_reviewers": [r.get("login") for r in details.get("requested_reviewers", [])],
        "commits": todays_commits(commits, day),
    }


def repo_prs_today(repo, day):
    """All PRs in `repo` updated on `day` (UTC), with details and commits."""
    owner, name = repo.split("/", 1)
    prs = []
    for summary in _paged(f"/repos/{owner}/{name}/pulls", {"state": "all", "sort": "updated", "direction": "desc"}):
        if not _is_today(summary["updated_at"], day):
            break  # sorted by updated desc: the first non-today PR ends today's window
        n = summary["number"]
        details, _ = _request(f"/repos/{owner}/{name}/pulls/{n}")
        commits = _paged(f"/repos/{owner}/{name}/pulls/{n}/commits")
        prs.append(pr_record(details, commits, day))
    return prs


def collect_activity(repos_file, users_file, day=None):
    """Map every user in users.txt to their PR work today on repos.txt repos."""
    day = day or datetime.now(timezone.utc).date()
    users = read_lines(users_file)
    activity = {u.lower(): {"username": u, "repos": {}} for u in users}

    for repo in read_lines(repos_file):
        if "/" not in repo:
            print(f"skipping malformed repo line: {repo!r} (expected owner/repo)")
            continue
        print(f"fetching PRs for {repo} ...")
        for pr in repo_prs_today(repo, day):
            for user, entry in activity.items():
                if user_participates(user, pr, pr["commits"]):
                    entry["repos"].setdefault(repo, {"pull_requests": []})["pull_requests"].append(pr)

    # sort PRs by number for stable output
    for entry in activity.values():
        for repo_data in entry["repos"].values():
            repo_data["pull_requests"].sort(key=lambda p: p["number"])
    return activity


if __name__ == "__main__":
    from pathlib import Path
    here = Path(__file__).resolve().parent
    data = collect_activity(here / "repos.txt", here / "users.txt")
    print(json.dumps(data, indent=2))
