from fastapi import APIRouter, Request, HTTPException
from src.model_serving.api.v1.schemas import WarmupRequest
from src.model_serving.services.inference_service import _resolve_active_version, _load_model_for_tenant, _get_base_pipeline
from src.model_serving.services.rerank_service import _get_reranker

router = APIRouter(prefix="/internal/v1", tags=["warmup"])


@router.post("/warmup")
async def warmup_endpoint(
    body: WarmupRequest,
    request: Request,
):
    tenant_id = getattr(request.state, "tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=403, detail="Tenant context not available")

    _get_reranker()

    if body.version_number is not None:
        version_info = _resolve_active_version(tenant_id)
        version_number = body.version_number
        artifact_path = version_info[0] if version_info else None
        if not artifact_path or artifact_path == "base":
            raise HTTPException(status_code=404, detail="No custom model found for this tenant")
    else:
        version_info = _resolve_active_version(tenant_id)
        if version_info is None:
            raise HTTPException(status_code=404, detail="No active model version found for this tenant")
        artifact_path, version_number = version_info

    if version_number == 0:
        _get_base_pipeline()
        return {"status": "ok", "version_number": 0}

    success = _load_model_for_tenant(tenant_id, version_number, artifact_path)
    if not success:
        raise HTTPException(status_code=404, detail=f"Model version v{version_number} could not be loaded")

    return {"status": "ok", "version_number": version_number}
