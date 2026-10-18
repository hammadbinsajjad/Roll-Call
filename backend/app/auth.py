"""Password hashing, JWT issue/verify, and the get_current_user dependency."""

from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import HTTPException, Request

from . import config, db

TOKEN_TTL_DAYS = 2  # decision Q8 — demo scope, re-login after 2 days


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def issue_token(username: str) -> str:
    if not config.JWT_SECRET:
        raise RuntimeError("JWT_SECRET is not set (backend/.env or environment).")
    payload = {"sub": username, "exp": datetime.now(UTC) + timedelta(days=TOKEN_TTL_DAYS)}
    return jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")


def get_current_user(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="unauthorized")
    if not config.JWT_SECRET:
        raise HTTPException(status_code=500, detail="server not configured")
    try:
        payload = jwt.decode(auth[7:], config.JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="unauthorized")
    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="unauthorized")
    request.state.username = username  # used as slowapi rate-limit key
    return username


def get_users_collection():
    return db.get_db()["users"]
