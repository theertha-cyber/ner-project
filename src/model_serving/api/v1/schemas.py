from pydantic import BaseModel


class InferRequest(BaseModel):
    tokens: list[str]


class TokenPrediction(BaseModel):
    token: str
    label: str
    confidence: float


class InferResponse(BaseModel):
    predictions: list[TokenPrediction]
    model_version: str | None = None


class WarmupRequest(BaseModel):
    version_number: int | None = None
