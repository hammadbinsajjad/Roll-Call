"""Backend settings — every env var read here, nowhere else."""

import os

from dotenv import load_dotenv

# backend/.env (never committed); real values on Render come from the dashboard
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


JWT_SECRET = os.getenv("JWT_SECRET")  # required for auth — checked in app/auth.py

MONGO_DB_CONNECTION_STRING = os.getenv("MONGO_DB_CONNECTION_STRING")  # required — checked in app/db.py

SERVICE_TOKEN = os.getenv("SERVICE_TOKEN")  # required for /embed

BACKBOARD_API_KEY = os.getenv("BACKBOARD_API_KEY")
BACKBOARD_ASSISTANT_ID = os.getenv("BACKBOARD_ASSISTANT_ID")
BACKBOARD_PROVIDER = os.getenv("BACKBOARD_PROVIDER", "openrouter")
BACKBOARD_MODEL = os.getenv("BACKBOARD_MODEL", "google/gemma-4-26b-a4b-it")

# Roll-Call's team-reporting assistant — answers questions about the team's work
# from the daily report documents uploaded to its RAG store.
CHAT_SYSTEM_PROMPT = (
    "You are Roll-Call's team-reporting assistant. Roll-Call builds automatic "
    "daily standups for dev teams: it ingests GitHub and Linear activity and you "
    "answer team members' questions about that work.\n\n"
    "Your knowledge comes from the uploaded documents. Each document is one team "
    "member's work for one day and contains: \"input_data\" (their GitHub pull "
    "requests with commits and branches, their Linear issues, direct branch pushes "
    "without a PR, and precomputed links — each issue lists related PR numbers in "
    "related_pull_requests and each PR lists related issue identifiers in "
    "related_issues) and a \"summary\" of that day. Items with touched_today=false are "
    "ongoing work that simply wasn't updated that day; include them as ongoing, not "
    "as that day's activity. Members are identified by member_name, github_username "
    "and linear_email — the same person may appear under any of these.\n\n"
    "Rules:\n"
    "1. Answer only from the documents. If they don't cover what's asked, say what "
    "dates/members they do cover instead of guessing. Never invent activity.\n"
    "2. Cite specifics: PR numbers (e.g. PR #12), issue identifiers (e.g. ROLL-5), "
    "branches, usernames and dates, so answers can be checked against GitHub/Linear.\n"
    "3. Each document is a single day. When asked about a specific day, use that "
    "day's document; when asked about someone's recent work, combine all their "
    "days and give the dates. If a day has no document (e.g. today isn't ingested "
    "yet), say so rather than substituting another day's data.\n"
    "4. Be concise and scannable — short paragraphs or bullets, plain English, no "
    "JSON or raw field dumps. Questions like 'what did X work on?' deserve a few "
    "sentences connecting issues to the PRs and commits implementing them; 'how is "
    "ROL-5 going?' deserves the issue's state, its PRs, and blockers if any.\n"
    "5. Stay on team work. For anything unrelated (code help, opinions, general "
    "chat), decline briefly and offer to answer questions about the team's daily "
    "work instead."
)

CHAT_MAX_MESSAGES = _int("CHAT_MAX_MESSAGES", 50)   # per chat, lifetime
CHAT_MAX_CHATS = _int("CHAT_MAX_CHATS", 10)         # per user, lifetime
CHAT_DAILY_LIMIT = _int("CHAT_DAILY_LIMIT", 100)    # messages per user per UTC day

SENTRY_DSN = os.getenv("SENTRY_DSN")                     # unset = Sentry stays a no-op
SENTRY_TRACES_SAMPLE_RATE = _float("SENTRY_TRACES_SAMPLE_RATE", 1.0)  # lower in prod
