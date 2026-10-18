"""/chats, /chat, /chat/{chat_id} — chat listing and turn-taking over a
Backboard thread. Message bodies live in Backboard; we store counts only."""

import json
import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sentry_sdk.ai import set_conversation_id
from slowapi import Limiter
from slowapi.util import get_remote_address

from .. import config, db
from ..auth import get_current_user
from ..models import ChatMessageRequest
from ..services import backboard

router = APIRouter()

limiter = Limiter(key_func=lambda request: getattr(request.state, "username", None)
                  or get_remote_address(request))

# The one tool the assistant gets: live team reports straight from daily_reports
# (no HTTP, no auth — executed in-process by _run_tool below).
DAILY_SUMMARIES_TOOL = {
    "type": "function",
    "function": {
        "name": "get_daily_summaries",
        "description": "Get every team member's work report for one day (UTC). "
                       "Source of truth for who worked on what, and when.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "ISO date YYYY-MM-DD; omit for today"},
            },
            "required": [],
        },
    },
}


def _run_tool(name, args) -> str:
    if name != "get_daily_summaries":
        return json.dumps({"error": "unknown tool"})
    raw = args.get("date") or db.today_iso()
    try:
        day = date.fromisoformat(raw).isoformat()
    except (TypeError, ValueError):
        return json.dumps({"error": "date must be ISO YYYY-MM-DD"})
    reports = list(db.get_db()["daily_reports"].find(
        {"date": day}, {"_id": 0, "date": 1, "member_name": 1, "github_username": 1,
                        "linear_email": 1, "input_data": 1, "summary": 1}))
    if not reports:
        return json.dumps({"error": f"no reports ingested for {day}"})
    return json.dumps(reports)


def _check_daily_limit(username: str):
    if db.daily_usage(username) >= config.CHAT_DAILY_LIMIT:
        raise HTTPException(status_code=429, detail="daily message limit reached")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@router.get("/chats")
def list_chats(username: str = Depends(get_current_user)):
    docs = (db.get_db()["chats"]
            .find({"username": username},
                  {"_id": 0, "chat_id": 1, "title": 1, "created_at": 1, "updated_at": 1})
            .sort("updated_at", -1))
    return list(docs)


@router.post("/chat")
@limiter.limit("10/minute")
def new_chat(request: Request, body: ChatMessageRequest, username: str = Depends(get_current_user)):
    # quotas checked before any Backboard call — rejected users cost us nothing
    _check_daily_limit(username)
    if db.get_db()["chats"].count_documents({"username": username}) >= config.CHAT_MAX_CHATS:
        raise HTTPException(status_code=429, detail="chat limit reached")

    try:
        reply, thread_id = backboard.send_message(
            body.message, tools=[DAILY_SUMMARIES_TOOL], tool_executor=_run_tool)
    except backboard.BackboardError:
        raise HTTPException(status_code=502, detail="AI service unavailable")
    if thread_id:
        set_conversation_id(thread_id)  # Sentry conversation = Backboard thread

    now = _now_iso()
    chat_id = uuid.uuid4().hex
    db.get_db()["chats"].insert_one({
        "chat_id": chat_id,
        "username": username,
        "thread_id": thread_id,   # Backboard-internal, never returned by any endpoint
        "title": body.message[:60],
        "message_count": 2,       # user + assistant
        "created_at": now,
        "updated_at": now,
    })
    db.bump_usage(username, 2)
    return {"chat_id": chat_id, "reply": reply}


@router.post("/chat/{chat_id}")
@limiter.limit("10/minute")
def continue_chat(request: Request, chat_id: str, body: ChatMessageRequest,
                  username: str = Depends(get_current_user)):
    _check_daily_limit(username)
    chat = db.get_db()["chats"].find_one({"chat_id": chat_id, "username": username})
    if not chat:
        raise HTTPException(status_code=404, detail="chat not found")
    if chat.get("message_count", 0) >= config.CHAT_MAX_MESSAGES:
        raise HTTPException(status_code=429, detail="message limit for this chat reached")

    if chat.get("thread_id"):
        set_conversation_id(chat["thread_id"])  # Sentry conversation = Backboard thread
    try:
        reply, _ = backboard.send_message(
            body.message, thread_id=chat.get("thread_id"),
            tools=[DAILY_SUMMARIES_TOOL], tool_executor=_run_tool)
    except backboard.BackboardError:
        raise HTTPException(status_code=502, detail="AI service unavailable")

    db.get_db()["chats"].update_one(
        {"_id": chat["_id"]},
        {"$inc": {"message_count": 2}, "$set": {"updated_at": _now_iso()}},
    )
    db.bump_usage(username, 2)
    return {"reply": reply}


@router.get("/chat/{chat_id}")
def get_chat(chat_id: str, username: str = Depends(get_current_user)):
    chat = db.get_db()["chats"].find_one({"chat_id": chat_id, "username": username})
    if not chat:
        raise HTTPException(status_code=404, detail="chat not found")
    thread_id = chat.get("thread_id")
    if not thread_id:
        raise HTTPException(status_code=404, detail="chat not found")
    try:
        messages = backboard.get_thread_messages(thread_id)
    except backboard.BackboardError:
        raise HTTPException(status_code=502, detail="AI service unavailable")
    return {"chat_id": chat_id, "messages": messages}
