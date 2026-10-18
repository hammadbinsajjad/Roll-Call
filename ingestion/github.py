"""GitHub activity collector — PR-walk based.

For each repo: walks all open PRs authored by the team's users; a PR is
touched today if it has commits authored today (fetched per PR branch —
feature-branch commits never show up in the default-branch commit list)
or was updated today (review/comment/merge). Others stay as ongoing work
(mirroring linear.py's ongoing issues). Commits pushed directly to the
default branch (outside PRs) are kept separately as "pushes".

Output, one entry per user identifier:

    {
        "<user>": {
            "username": "<user>",
            "repos": {
                "owner/repo": {
                    "pull_requests": [{..., "touched_today": ..., "commits": [...]}],
                    "pushes": [{...commit...}]
                }
            }
        }
    }
"""

import json
import os
import re
import time
from datetime import UTC, date, datetime

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


def _is_today(iso_ts, day):
    """GitHub timestamps are ISO 8601 in UTC; 'today' means the UTC day."""
    return iso_ts[:10] == day.isoformat()


def commits_today(repo, day):
    """All commits on the repo's default branch on `day` (UTC) — server-side
    date filter. Only used for standalone pushes: PR-branch commits never
    show up here."""
    owner, name = repo.split("/", 1)
    start = f"{day.isoformat()}T00:00:00Z"
    yield from _paged(f"/repos/{owner}/{name}/commits", {"since": start})


def todays_commits(commits, day):
    """Keep only commits authored on `day` (UTC), slimmed down. Filters on
    the author date, so commits authored earlier but pushed today are
    excluded — 'work done today' means authored today."""
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
    """All (login, email) identifiers that appear as commit authors."""
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


def user_participates(user, pr, pr_commits):
    """User touched this PR if they authored it, authored a commit on it,
    or were requested as reviewer / assigned. Works on both raw details
    and the slim records from pr_record()."""
    u = user.lower()
    author = pr.get("author") or (pr.get("user") or {}).get("login")
    if author and author.lower() == u:
        return True
    if u in _commit_identifiers(pr_commits):
        return True
    reviewers = {
        (r.get("login") or "").lower() if isinstance(r, dict) else str(r).lower()
        for r in pr.get("requested_reviewers", [])
    }
    assignees = {
        (r.get("login") or "").lower() if isinstance(r, dict) else str(r).lower()
        for r in pr.get("assignees", [])
    }
    return u in reviewers or u in assignees


def pr_record(details, commits, day, touched_today=True):
    """Slimmed-down PR dict; commits filtered to today's when touched_today."""
    return {
        "number": details["number"],
        "title": details["title"],
        "body": details.get("body"),  # PR description (may be None if none was written)
        "state": details["state"],
        "merged": details.get("merged", False),
        "draft": details.get("draft", False),
        "html_url": details["html_url"],
        "branch": (details.get("head") or {}).get("ref"),  # needed to link PRs to Linear issues
        "author": (details.get("user") or {}).get("login"),
        "created_at": details["created_at"],
        "updated_at": details["updated_at"],
        "requested_reviewers": [r.get("login") for r in details.get("requested_reviewers", [])],
        "touched_today": touched_today,
        "commits": todays_commits(commits, day) if touched_today else [],
    }


def repo_activity_today(repo, users_lower, day):
    """(touched_prs, ongoing_prs, standalone_pushes) for one repo today."""
    owner, name = repo.split("/", 1)
    base = f"/repos/{owner}/{name}"

    # direct pushes to the default branch today (excluding PR-merge commits)
    raw_pushes = [
        c for c in commits_today(repo, day)
        if len(c.get("parents", [])) <= 1
    ]
    pushes = todays_commits(raw_pushes, day)

    touched, ongoing = [], []
    for summary in _paged(f"{base}/pulls", {"state": "open", "direction": "desc"}):
        if (summary.get("user") or {}).get("login", "").lower() not in users_lower:
            continue
        # PR-branch commits; filtered to today locally (no `since` support here)
        pr_commits_raw = list(_paged(f"{base}/pulls/{summary['number']}/commits"))
        if todays_commits(pr_commits_raw, day) or _is_today(summary["updated_at"], day):
            # details add requested_reviewers and the full head data
            details, _ = _request(f"{base}/pulls/{summary['number']}")
            touched.append(pr_record(details, pr_commits_raw, day, touched_today=True))
        else:
            ongoing.append(pr_record(summary, [], day, touched_today=False))

    # closed PRs updated today (merged today is a key daily event); bounded
    # walk: sorted by updated desc, the first non-today PR ends the window
    for summary in _paged(f"{base}/pulls", {"state": "closed", "sort": "updated", "direction": "desc"}):
        if not _is_today(summary["updated_at"], day):
            break
        if (summary.get("user") or {}).get("login", "").lower() not in users_lower:
            continue
        pr_commits_raw = list(_paged(f"{base}/pulls/{summary['number']}/commits"))
        details, _ = _request(f"{base}/pulls/{summary['number']}")
        touched.append(pr_record(details, pr_commits_raw, day, touched_today=True))

    return touched, ongoing, pushes


def collect_github_activity(repos, users, day=None):
    """Map every user id to their GitHub work today on the given repos.

    repos: ["owner/repo", ...], users: ["login or email", ...] — same
    shapes db.get_repos() / db.get_team_members() deliver.
    """
    day = day or datetime.now(UTC).date()
    users_lower = {u.lower() for u in users}
    activity = {u.lower(): {"username": u, "repos": {}} for u in users}

    for repo in repos:
        if "/" not in repo:
            print(f"skipping malformed repo: {repo!r} (expected owner/repo)")
            continue
        print(f"fetching PRs for {repo} ...")
        touched, ongoing, pushes = repo_activity_today(repo, users_lower, day)

        for user, entry in activity.items():
            repo_entry = entry["repos"].setdefault(repo, {"pull_requests": [], "pushes": []})
            for pr in touched + ongoing:
                if user_participates(user, pr, pr["commits"]):
                    repo_entry["pull_requests"].append(pr)
            if user in users_lower and any(
                user in _commit_identifiers([c]) for c in pushes
            ):
                repo_entry["pushes"].extend(
                    c for c in pushes if user in _commit_identifiers([c])
                )

    # stable ordering
    for entry in activity.values():
        for repo_data in entry["repos"].values():
            repo_data["pull_requests"].sort(key=lambda p: p["number"])
            repo_data["pushes"].sort(key=lambda c: c["date"] or "")
    return activity


if __name__ == "__main__":
    # standalone debugging: hardcoded sample values, same as db.py placeholders
    from dotenv import load_dotenv
    load_dotenv()
    data = collect_github_activity(
        ["hammadbinsajjad/Roll-Call"],
        ["hammadbinsajjad", "supperhammad2002@gmail.com"],
    )
    print(json.dumps(data, indent=2))
