from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from src.model_serving.api.v1.schemas import InferRequest, InferResponse, TokenPrediction
from src.model_serving.services.inference_service import infer

router = APIRouter(prefix="/internal/v1", tags=["inference"])


def get_tenant_id(request: Request) -> str:
    tid = getattr(request.state, "tenant_id", None)
    if tid is None:
        raise HTTPException(status_code=403, detail="Tenant context not available")
    return tid


@router.post("/infer", response_model=InferResponse)
async def inference_endpoint(
    body: InferRequest,
    request: Request,
):
    tenant_id = get_tenant_id(request)

    predictions, model_version = infer(tenant_id, body.tokens)
    if predictions is None:
        raise HTTPException(
            status_code=404,
            detail="No model available for this tenant",
        )

    pred_objects = [TokenPrediction(**r) for r in predictions]
    headers = {}
    if model_version == "0":
        headers["X-Model-Source"] = "base"
    return JSONResponse(
        content=InferResponse(predictions=[p.model_dump() for p in pred_objects], model_version=model_version).model_dump(),
        headers=headers,
    )
