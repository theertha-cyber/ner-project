from pydantic import BaseModel


class InferRequest(BaseModel):
    tokens: list[str]


class TokenPrediction(BaseModel):
    token: str
    label: str
    confidence: float


class InferResponse(BaseModel):
    predictions: list[TokenPrediction]


class WarmupRequest(BaseModel):
    version_number: int | None = None
