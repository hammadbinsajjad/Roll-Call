"""Thin REST client over the Backboard API.

Endpoints used:
  POST /threads/messages                    — send a chat message (returns reply + thread_id)
  GET  /threads/{thread_id}/messages        — chat history (serves GET /chat/{id})
  GET  /assistants/{id}/documents           — list assistant documents (idempotent re-ingest)
  DELETE /documents/{id}                    — drop a document
  POST /assistants/{id}/documents (multipart) — upload a document

Errors are wrapped in BackboardError; routers map it to 502 without leaking details.
"""

import hashlib
import json

import httpx

from .. import config


class BackboardError(Exception):
    pass


def _config_error(name: str):
    raise BackboardError(f"{name} is not configured")


def _headerless_post(path: str, json_body: dict | None = None, timeout: float = 60.0):
    if not config.BACKBOARD_API_KEY:
        _config_error("BACKBOARD_API_KEY")
    url = f"https://app.backboard.io/api{path}"
    return httpx.post(
        url,
        json=json_body,
        headers={"X-API-Key": config.BACKBOARD_API_KEY},
        timeout=timeout,
    )


def _get(path: str):
    if not config.BACKBOARD_API_KEY:
        _config_error("BACKBOARD_API_KEY")
    url = f"https://app.backboard.io/api{path}"
    return httpx.get(url, headers={"X-API-Key": config.BACKBOARD_API_KEY}, timeout=60.0)


def _first_str(data, keys):
    """Pull the first string-valued key out of a dict, tolerating nested wrappers."""
    if isinstance(data, dict):
        for key in keys:
            value = data.get(key)
            if isinstance(value, str):
                return value
            if isinstance(value, dict):
                nested = _first_str(value, keys)
                if nested:
                    return nested
    return None


def send_message(content: str, thread_id: str | None = None) -> tuple[str, str | None]:
    """Send one chat turn. Returns (reply_text, thread_id).

    New chats omit thread_id — Backboard creates the thread and returns it.
    """
    if not config.BACKBOARD_ASSISTANT_ID:
        _config_error("BACKBOARD_ASSISTANT_ID")
    body = {
        "assistant_id": config.BACKBOARD_ASSISTANT_ID,
        "content": content,
        "system_prompt": config.CHAT_SYSTEM_PROMPT,
        "provider": config.BACKBOARD_PROVIDER,
        "model": config.BACKBOARD_MODEL,
        "stream": False,
        "memory": "off",  # shared per-assistant memory would leak between users
    }
    if thread_id:
        body["thread_id"] = thread_id
    try:
        resp = _headerless_post("/threads/messages", body)
    except httpx.HTTPError as exc:
        raise BackboardError(f"Backboard request failed: {exc}") from exc
    if resp.status_code >= 400:
        raise BackboardError(f"Backboard returned {resp.status_code}")
    data = resp.json() if resp.content else {}
    reply = _first_str(data, ("reply", "content", "text", "message"))
    if not reply:
        raise BackboardError(f"unexpected Backboard response shape: {list(data)!r}")
    new_thread_id = data.get("thread_id")
    if not new_thread_id and isinstance(data.get("thread"), dict):
        new_thread_id = data["thread"].get("id")
    return reply, new_thread_id


def get_thread_messages(thread_id: str) -> list[dict]:
    """Fetch a thread's history, mapped to [{role, content, created_at}]."""
    try:
        resp = _get(f"/threads/{thread_id}/messages")
    except httpx.HTTPError as exc:
        raise BackboardError(f"Backboard request failed: {exc}") from exc
    if resp.status_code >= 400:
        raise BackboardError(f"Backboard returned {resp.status_code}")
    data = resp.json() if resp.content else []
    items = data if isinstance(data, list) else (data.get("messages") or data.get("data") or [])
    messages = []
    for item in items:
        if not isinstance(item, dict):
            continue
        content = _first_str(item, ("content", "text"))
        if not content:
            continue
        role = item.get("role")
        if not role and item.get("is_assistant") is not None:
            role = "assistant" if item.get("is_assistant") else "user"
        messages.append({
            "role": role or "assistant",
            "content": content,
            "created_at": item.get("created_at"),
        })
    return messages


def _list_documents():
    if not config.BACKBOARD_ASSISTANT_ID:
        _config_error("BACKBOARD_ASSISTANT_ID")
    try:
        resp = _get(f"/assistants/{config.BACKBOARD_ASSISTANT_ID}/documents")
    except httpx.HTTPError as exc:
        raise BackboardError(f"Backboard request failed: {exc}") from exc
    if resp.status_code >= 400:
        raise BackboardError(f"Backboard returned {resp.status_code}")
    data = resp.json() if resp.content else []
    items = data if isinstance(data, list) else (data.get("documents") or data.get("data") or [])
    docs = []
    for item in items:
        if isinstance(item, dict):
            doc_id = item.get("id") or item.get("document_id")
            name = item.get("filename") or item.get("name")
            if doc_id:
                docs.append({"id": doc_id, "filename": name})
    return docs


def _delete_document(doc_id: str):
    if not config.BACKBOARD_API_KEY:
        _config_error("BACKBOARD_API_KEY")
    url = f"https://app.backboard.io/api/documents/{doc_id}"
    try:
        resp = httpx.delete(url, headers={"X-API-Key": config.BACKBOARD_API_KEY}, timeout=60.0)
    except httpx.HTTPError as exc:
        raise BackboardError(f"Backboard request failed: {exc}") from exc
    if resp.status_code >= 400:
        raise BackboardError(f"Backboard returned {resp.status_code}")


def upload_document(data, filename: str | None = None) -> dict:
    """Upload a JSON blob as one document. Deletes an existing doc with the
    same filename first, so re-runs replace instead of piling up duplicates."""
    payload = json.dumps(data, default=str)
    if not filename:
        filename = hashlib.sha256(payload.encode()).hexdigest()[:16] + ".json"
    for doc in _list_documents():
        if doc["filename"] == filename:
            _delete_document(doc["id"])
            break
    try:
        resp = httpx.post(
            f"https://app.backboard.io/api/assistants/{config.BACKBOARD_ASSISTANT_ID}/documents",
            files={"file": (filename, payload, "application/json")},
            headers={"X-API-Key": config.BACKBOARD_API_KEY},
            timeout=60.0,
        )
    except httpx.HTTPError as exc:
        raise BackboardError(f"Backboard request failed: {exc}") from exc
    if resp.status_code >= 400:
        raise BackboardError(f"Backboard returned {resp.status_code}")
    doc = resp.json() if resp.content else {}
    return {
        "document_id": doc.get("id") or doc.get("document_id"),
        "filename": filename,
        "status": doc.get("status", "pending"),
    }
