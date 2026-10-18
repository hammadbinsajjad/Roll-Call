"""/member-summary — read-only over the ingestion-owned daily_reports
collection (one endpoint: all members for a day; the FE never asks per-member)."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from ..auth import get_current_user
from ..db import get_db

router = APIRouter()

_PROJECTION = {"_id": 0, "member_name": 1, "github_username": 1, "linear_email": 1, "date": 1, "summary": 1}


@router.get("/member-summary")
def summaries_for_date(date: str, username: str = Depends(get_current_user)):
    if not date:
        raise HTTPException(status_code=400, detail="date is required")
    try:
        iso = date.fromisoformat(date).isoformat()
    except ValueError:
        raise HTTPException(status_code=400, detail="date must be an ISO date (YYYY-MM-DD)")
    return list(get_db()["daily_reports"].find({"date": iso}, _PROJECTION))
