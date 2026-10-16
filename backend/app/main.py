from fastapi import FastAPI

app = FastAPI(title="Roll-Call API")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
