"""Roll-Call API — app creation, CORS, rate limiting, error handling.

Every error response is {"error": "<message>"} (the FE contract);
FastAPI's default {"detail": ...} would break the frontend.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import config, db
from .routers import auth, chats, config as config_router, embed, member_summary


@asynccontextmanager
async def lifespan(application: FastAPI):
    db.get_db()  # fail fast on a bad connection string + set up indexes
    yield


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": message})


limiter = chats.limiter  # single shared limiter (keyed by username or IP)

app = FastAPI(title="Roll-Call API", lifespan=lifespan)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # public demo — accept browsers from any origin
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return _error(429, "rate limit exceeded")


@app.exception_handler(StarletteHTTPException)
def http_error(request: Request, exc: StarletteHTTPException):
    message = exc.detail if isinstance(exc.detail, str) else "error"
    return _error(exc.status_code, message)


@app.exception_handler(RequestValidationError)
def validation_error(request: Request, exc: RequestValidationError):
    return _error(400, "invalid request")


@app.exception_handler(Exception)
def unhandled_error(request: Request, exc: Exception):
    return _error(500, "internal server error")


app.include_router(auth.router)
app.include_router(config_router.router)
app.include_router(member_summary.router)
app.include_router(chats.router)
app.include_router(embed.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
