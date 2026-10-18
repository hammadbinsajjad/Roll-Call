"""Offline asserts for the filtering/matching logic in github.py (no network)."""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from github import (_commit_identifiers, pr_record, todays_commits, user_participates)

TODAY = date(2026, 3, 10)

commits = [
    {"sha": "a", "commit": {"author": {"date": "2026-03-10T12:00:00Z", "email": "dev@x.com", "name": "Dev"}, "message": "fix bug"}, "author": {"login": "devuser"}},
    {"sha": "b", "commit": {"author": {"date": "2026-03-09T12:00:00Z", "email": "dev@x.com", "name": "Dev"}, "message": "old work"}, "author": {"login": "devuser"}},
    {"sha": "c", "commit": {"author": {"date": "2026-03-10T08:00:00Z", "email": "other@x.com", "name": "Other"}, "message": "other"}, "author": {"login": "otheruser"}},
]

kept = todays_commits(commits, TODAY)
assert [c["sha"] for c in kept] == ["a", "c"], kept

assert _commit_identifiers(commits) == {"devuser", "dev@x.com", "otheruser", "other@x.com"}

pr = {"user": {"login": "someoneelse"}, "requested_reviewers": [], "assignees": []}
assert not user_participates("devuser", pr, todays_commits(commits, date(2026, 3, 11)))  # no commits that day
assert user_participates("devuser", pr, todays_commits(commits, TODAY))                   # via today's commit
assert user_participates("dev@x.com", pr, commits)         # via email
assert user_participates("DevUser", {"user": {"login": "devuser"}, "requested_reviewers": [], "assignees": []}, [])  # case-insensitive raw
assert user_participates("devuser", {"author": "devuser", "requested_reviewers": [], "assignees": []}, [])  # slim record author
assert user_participates("reviewer", {"author": "x", "requested_reviewers": ["Reviewer"], "assignees": []}, [])  # slim reviewer strings
assert user_participates("reviewer", {"author": "x", "requested_reviewers": [{"login": "Reviewer"}], "assignees": []}, [])  # raw reviewer dicts

rec = pr_record(
    {"number": 7, "title": "t", "state": "open", "html_url": "u", "user": {"login": "devuser"},
     "created_at": "2026-03-10T00:00:00Z", "updated_at": "2026-03-10T01:00:00Z",
     "head": {"ref": "feature/x"}, "requested_reviewers": [], "body": None},
    commits, TODAY,
)
assert rec["branch"] == "feature/x" and rec["touched_today"] is True
assert [c["sha"] for c in rec["commits"]] == ["a", "c"]
old_pr = pr_record(rec, [], TODAY, touched_today=False)
assert old_pr["touched_today"] is False and old_pr["commits"] == []

# comment-preserving read of repos.txt / users.txt
print("all asserts passed")
