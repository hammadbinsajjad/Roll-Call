"""Roll-Call data ingestion entry point.

Collects per-developer activity (currently from GitHub, later plus a
second source) and hands everything to the LLM layer (llm.py) to build
the human-readable daily report.
"""

from dotenv import load_dotenv

from github import collect_activity
from linear import collect_activity as collect_linear_activity
from llm import build_report


def collect_other_activity() -> dict:
    """Second ingestion source: Linear issues (linear.py)."""
    return collect_linear_activity("users.txt")


def main():
    load_dotenv()  # picks up GITHUB_TOKEN from ingestion/.env
    github_activity = collect_activity(
        "repos.txt",
        "users.txt",
    )
    other_activity = collect_other_activity()
    report = build_report(github_activity, other_activity)
    print(report)


if __name__ == "__main__":
    main()
