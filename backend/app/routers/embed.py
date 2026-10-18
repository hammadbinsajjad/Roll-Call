"""/embed — machine-to-machine endpoint for the ingestion pipeline.
Auth is a shared secret header (X-Service-Token), not a user JWT."""

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from .. import config
from ..models import EmbedRequest
from ..services import backboard

router = APIRouter()

limiter = Limiter(key_func=get_remote_address)


def require_service_token(request: Request) -> None:
    if not config.SERVICE_TOKEN:
        raise HTTPException(status_code=500, detail="server not configured")
    if request.headers.get("X-Service-Token") != config.SERVICE_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")


@router.post("/embed")
@limiter.limit("20/minute")
def embed(request: Request, body: EmbedRequest,
          _token: None = Depends(require_service_token)):
    try:
        doc = backboard.upload_document(body.data, body.filename)
    except backboard.BackboardError:
        raise HTTPException(status_code=502, detail="AI service unavailable")
    return doc
