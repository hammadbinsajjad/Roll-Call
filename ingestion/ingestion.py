"""Roll-Call data ingestion entry point.

The orchestrator: the only place the supporting modules talk to each
other. Gets the team and repos from the DB (db.py), collects activity
from GitHub (github.py) and Linear (linear.py), sends each member's
combined data to the LLM (llm.py), and stores the per-member input and
summary back in the DB.
"""

from dotenv import load_dotenv

import db
from github import collect_github_activity
from linear import collect_linear_activity
from llm import build_reports


def main():
    load_dotenv()  # picks up GITHUB_TOKEN, LINEAR_TOKEN, OPENAI_API_KEY, LLM_* from ingestion/.env

    repos = db.get_repos()
    members = db.get_team_members()
    if not members:
        raise RuntimeError("db.get_team_members() returned no members — DB not set up yet.")

    github_activity = collect_github_activity(
        repos,
        [m["github_username"] for m in members if m.get("github_username")],
    )
    linear_activity = collect_linear_activity(
        [m["linear_email"] for m in members if m.get("linear_email")],
    )

    for result in build_reports(members, github_activity, linear_activity):
        db.store_member_data(result["member"], result["input_data"], result["summary"])
        print(f"=== {result['member']['member_name']} ===")
        print(result["summary"])


if __name__ == "__main__":
    main()
