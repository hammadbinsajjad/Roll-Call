"""/chats, /chat, /chat/{chat_id} — chat listing and turn-taking over a
Backboard thread. Message bodies live in Backboard; we store counts only."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from .. import config, db
from ..auth import get_current_user
from ..models import ChatMessageRequest
from ..services import backboard

router = APIRouter()

limiter = Limiter(key_func=lambda request: getattr(request.state, "username", None)
                  or get_remote_address(request))


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
        reply, thread_id = backboard.send_message(body.message)
    except backboard.BackboardError:
        raise HTTPException(status_code=502, detail="AI service unavailable")

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

    try:
        reply, _ = backboard.send_message(body.message, thread_id=chat.get("thread_id"))
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
