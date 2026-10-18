"""/member-summary and /member-summary/{member_id} — read-only over the
ingestion-owned daily_reports collection."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from ..auth import get_current_user
from ..db import get_db

router = APIRouter()

_PROJECTION = {"_id": 0, "member_name": 1, "github_username": 1, "linear_email": 1, "date": 1, "summary": 1}


def _iso_date(raw: str) -> str:
    try:
        return date.fromisoformat(raw).isoformat()
    except ValueError:
        raise HTTPException(status_code=400, detail="date must be an ISO date (YYYY-MM-DD)")


@router.get("/member-summary")
def summaries_for_date(date: str, username: str = Depends(get_current_user)):
    if not date:
        raise HTTPException(status_code=400, detail="date is required")
    return list(get_db()["daily_reports"].find({"date": _iso_date(date)}, _PROJECTION))


@router.get("/member-summary/{member_id}")
def summary_for_member(member_id: str, date: str | None = None, username: str = Depends(get_current_user)):
    query = {"$or": [{"github_username": member_id}, {"linear_email": member_id}]}
    if date:
        query["date"] = _iso_date(date)
    # no date given → the member's latest report
    doc = next(iter(get_db()["daily_reports"].find(query, _PROJECTION).sort("date", -1).limit(1)), None)
    if not doc:
        raise HTTPException(status_code=404, detail="no report found for this member")
    return doc
