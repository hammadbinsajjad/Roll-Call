"""Roll-Call data ingestion entry point.

The orchestrator: the only place the supporting modules talk to each
other. Gets the team and repos from the DB (db.py), collects activity
from GitHub (github.py) and Linear (linear.py), sends each member's
combined data to the LLM (llm.py), and stores the per-member input and
summary back in the DB.

Reports "today" (UTC) by default; set INGESTION_DAY=YYYY-MM-DD to report
another day (used by the nightly GitHub workflow).
"""

from datetime import date
import os

from dotenv import load_dotenv

import db
from github import collect_github_activity
from linear import collect_linear_activity
from llm import build_reports


def _ingestion_day():
    """UTC day to report. INGESTION_DAY (ISO date) overrides for scheduled
    nightly runs, which report the completed previous day."""
    raw = os.getenv("INGESTION_DAY")
    if not raw:
        return None  # collectors default to today (UTC)
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise SystemExit(f"INGESTION_DAY must be an ISO date (YYYY-MM-DD), got {raw!r}") from exc


def main():
    load_dotenv()  # picks up GITHUB_TOKEN, LINEAR_TOKEN, OPENAI_API_KEY, LLM_* from ingestion/.env

    repos = db.get_repos()
    members = db.get_team_members()
    if not members:
        raise RuntimeError("db.get_team_members() returned no members — DB not set up yet.")

    day = _ingestion_day()
    github_activity = collect_github_activity(
        repos,
        [m["github_username"] for m in members if m.get("github_username")],
        day=day,
    )
    linear_activity = collect_linear_activity(
        [m["linear_email"] for m in members if m.get("linear_email")],
        day=day,
    )

    for result in build_reports(members, github_activity, linear_activity):
        db.store_member_data(result["member"], result["input_data"], result["summary"])
        print(f"=== {result['member']['member_name']} ===")
        print(result["summary"])


if __name__ == "__main__":
    main()
