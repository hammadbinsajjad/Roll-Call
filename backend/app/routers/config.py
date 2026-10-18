"""/config + /config/repos + /config/members — read/write the shared
repos and team_members collections (same shape the ingestion reads)."""

from fastapi import APIRouter, Depends

from ..auth import get_current_user
from ..db import get_db
from ..models import DeleteMemberRequest, DeleteRepoRequest, MemberRequest, RepoRequest

router = APIRouter()

_MEMBER_FIELDS = ("github_username", "linear_email", "member_name")


def _config_response() -> dict:
    d = get_db()
    return {
        "repos": [doc["name"] for doc in d["repos"].find({}, {"_id": 0, "name": 1}) if doc.get("name")],
        "team_members": [
            {k: doc.get(k) for k in _MEMBER_FIELDS}
            for doc in d["team_members"].find({}, {"_id": 0})
            if all(doc.get(k) for k in _MEMBER_FIELDS)
        ],
    }


@router.get("/config")
def get_config(username: str = Depends(get_current_user)):
    return _config_response()


@router.post("/config/repos")
def add_repo(body: RepoRequest, username: str = Depends(get_current_user)):
    get_db()["repos"].update_one({"name": body.name}, {"$set": {"name": body.name}}, upsert=True)
    return {"ok": True, "repos": _config_response()["repos"]}


@router.delete("/config/repos")
def remove_repo(body: DeleteRepoRequest, username: str = Depends(get_current_user)):
    get_db()["repos"].delete_one({"name": body.name})
    return {"ok": True, "repos": _config_response()["repos"]}


@router.post("/config/members")
def upsert_member(body: MemberRequest, username: str = Depends(get_current_user)):
    doc = {k: getattr(body, k) for k in _MEMBER_FIELDS}
    # the mock keyed members on github_username — keep that keying
    get_db()["team_members"].replace_one({"github_username": body.github_username}, doc, upsert=True)
    return {"ok": True, "team_members": _config_response()["team_members"]}


@router.delete("/config/members")
def remove_member(body: DeleteMemberRequest, username: str = Depends(get_current_user)):
    get_db()["team_members"].delete_one({"github_username": body.github_username})
    return {"ok": True, "team_members": _config_response()["team_members"]}
