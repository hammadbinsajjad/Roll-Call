"""/auth/register, /auth/login"""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from pymongo.errors import DuplicateKeyError

from .. import db
from ..auth import hash_password, issue_token, verify_password
from ..models import LoginRequest, RegisterRequest

router = APIRouter()


@router.post("/auth/register", status_code=201)
def register(body: RegisterRequest):
    try:
        db.get_db()["users"].insert_one({
            "username": body.username,
            "password_hash": hash_password(body.password),
            "created_at": datetime.now(UTC).isoformat(),
            "usage_date": db.today_iso(),
            "usage_count": 0,
        })
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="username already taken")
    return {"token": issue_token(body.username), "username": body.username}


@router.post("/auth/login")
def login(body: LoginRequest):
    user = db.get_db()["users"].find_one({"username": body.username})
    if not user or not verify_password(body.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="invalid username or password")
    return {"token": issue_token(user["username"]), "username": user["username"]}
