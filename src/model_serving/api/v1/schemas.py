from pydantic import BaseModel


class InferRequest(BaseModel):
    tokens: list[str]


class TokenPrediction(BaseModel):
    token: str
    label: str
    confidence: float
    # Index of this prediction's word in the request's `tokens` list. Present on the
    # fine-tuned (ONNX) path, where predictions are per whitespace word; None on the
    # base-model pipeline path, whose outputs are WordPieces with no word alignment.
    word_index: int | None = None


class InferResponse(BaseModel):
    predictions: list[TokenPrediction]
    model_version: str | None = None


class WarmupRequest(BaseModel):
    version_number: int | None = None


class RerankRequest(BaseModel):
    query: str
    documents: list[str]
    top_k: int | None = None


class RerankResult(BaseModel):
    index: int
    score: float


class RerankResponse(BaseModel):
    results: list[RerankResult]
