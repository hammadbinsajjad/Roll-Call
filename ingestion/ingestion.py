"""Roll-Call data ingestion entry point.

Collects per-developer activity from GitHub (PRs and commits) and from
Linear (issues and comments), then hands both to the LLM layer to build
the human-readable daily report.
"""

from dotenv import load_dotenv

from github import collect_github_activity
from linear import collect_linear_activity
from llm import build_report


def main():
    load_dotenv()  # picks up GITHUB_TOKEN and LINEAR_TOKEN from ingestion/.env
    github_activity = collect_github_activity("repos.txt", "users.txt")
    linear_activity = collect_linear_activity("users.txt")
    report = build_report(github_activity, linear_activity)
    print(report)


if __name__ == "__main__":
    main()
