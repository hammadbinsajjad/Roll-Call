from pydantic import BaseModel, Field


class EmbedRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Text to embed")

    def run(self) -> list[float]:
        # placeholder — real embedding logic lands here later
        return []
