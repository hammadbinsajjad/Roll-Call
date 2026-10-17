from fastapi import FastAPI
from pydantic import BaseModel

from app.domain.embed import EmbedRequest

app = FastAPI(title="Roll-Call API")


class EmbedResponse(BaseModel):
    vector: list[float]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/embed")
def embed(request: EmbedRequest) -> EmbedResponse:
    return EmbedResponse(vector=request.run())
