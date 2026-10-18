"""DB layer for Roll-Call ingestion.

Placeholder until the database is set up: the functions below return the
values that used to live in repos.txt / users.txt so the pipeline keeps
running identically. The DB-driven change later is only inside this file
— the rest of the ingestion expects exactly these signatures.
"""


def get_repos():
    """Return the repos to monitor as ["owner/repo", ...]."""
    # TODO: read from the DB
    return ["hammadbinsajjad/Roll-Call"]


def get_team_members():
    """Return the team as a list of dicts, one per member:

        [{"github_username": ..., "linear_email": ..., "member_name": ...}]

    github_username maps the member into the GitHub ingestion's activity,
    linear_email into the Linear ingestion's activity; member_name labels
    the stored/generated reports.
    """
    # TODO: read from the DB
    return [
        {
            "github_username": "hammadbinsajjad",
            "linear_email": "supperhammad2002@gmail.com",
            "member_name": "Hammad Bin Sajjad",
        }
    ]


def store_member_data(member, input_data, summary):
    """Store one member's day: their LLM input data and the generated summary."""
    # TODO: implement when the DB exists
    return None
