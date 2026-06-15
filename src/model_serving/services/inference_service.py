import os
import numpy as np
import onnxruntime as ort
from transformers import AutoTokenizer
from src.model_serving.services.model_cache import model_cache
from src.model_serving.services.model_loader import download_model_artifacts, estimate_model_memory
from src.shared.config import settings

BASE_MODEL = "dslim/bert-base-NER"
_tokenizer = None


def _get_tokenizer():
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    return _tokenizer


def _resolve_active_version(tenant_id: str) -> tuple[str, int] | None:
    import requests
    from src.shared.auth import create_access_token

    token = create_access_token(tenant_id=tenant_id, user_id="model-serving", role="system_admin")
    registry_url = f"http://training_service:8003/api/v1/models/active"
    try:
        resp = requests.get(
            registry_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        return data["artifact_path"], data["version_number"]
    except requests.RequestException:
        return None


def _load_model_for_tenant(tenant_id: str, version_number: int) -> bool:
    model_id = f"{tenant_id}_v{version_number}"
    cached = model_cache.get(model_id)
    if cached is not None:
        return True

    local_dir = download_model_artifacts(tenant_id, version_number)
    memory = estimate_model_memory(local_dir)

    onnx_path = None
    for root, dirs, files in os.walk(local_dir):
        for f in files:
            if f.endswith(".onnx"):
                onnx_path = os.path.join(root, f)
                break
        if onnx_path:
            break

    if onnx_path is None:
        import shutil
        shutil.rmtree(local_dir, ignore_errors=True)
        return False

    session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    model_cache.put(model_id, {"session": session, "local_dir": local_dir}, memory)
    return True


def infer(tenant_id: str, tokens: list[str]) -> list[dict] | None:
    version_info = _resolve_active_version(tenant_id)
    if version_info is None:
        return None

    artifact_path, version_number = version_info
    model_id = f"{tenant_id}_v{version_number}"

    cached = model_cache.get(model_id)
    if cached is None:
        loaded = _load_model_for_tenant(tenant_id, version_number)
        if not loaded:
            return None
        cached = model_cache.get(model_id)

    session = cached.model["session"]
    tokenizer = _get_tokenizer()

    encoding = tokenizer(
        tokens,
        is_split_into_words=True,
        truncation=True,
        padding=True,
        return_tensors="np",
    )

    input_ids = encoding["input_ids"].astype(np.int64)
    attention_mask = encoding["attention_mask"].astype(np.int64)
    token_type_ids = encoding.get("token_type_ids", None)

    inputs = {"input_ids": input_ids, "attention_mask": attention_mask}
    if token_type_ids is not None:
        inputs["token_type_ids"] = token_type_ids.astype(np.int64)

    outputs = session.run(None, inputs)
    logits = outputs[0]

    predicted_ids = logits.argmax(axis=-1)[0]
    scores = np.max(logits, axis=-1)[0]

    word_ids = encoding.word_ids(0)
    id2label = tokenizer.model_max_length
    config = tokenizer.model_max_length

    label_list = _resolve_label_list(tenant_id)
    if not label_list:
        return None

    results = []
    seen_words = set()
    for token_idx, (word_id, pred_id, prob) in enumerate(zip(word_ids, predicted_ids, scores)):
        if word_id is None:
            continue
        if word_id in seen_words:
            continue
        if pred_id == 0:
            seen_words.add(word_id)
            continue

        seen_words.add(word_id)
        label = label_list[pred_id] if pred_id < len(label_list) else f"LABEL_{pred_id}"
        results.append({
            "token": tokens[word_id],
            "label": label,
            "confidence": float(prob),
        })

    return results


_label_list_cache: dict[str, list[str]] = {}
_label_list_ttl: dict[str, float] = {}
import time


def _resolve_label_list(tenant_id: str) -> list[str]:
    now = time.monotonic()
    cached = _label_list_cache.get(tenant_id)
    ttl = _label_list_ttl.get(tenant_id, 0)
    if cached is not None and now < ttl:
        return cached

    import requests
    from src.shared.auth import create_access_token

    token = create_access_token(tenant_id=tenant_id, user_id="model-serving", role="system_admin")
    registry_url = f"http://training_service:8003/api/v1/models/active"
    try:
        resp = requests.get(
            registry_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if resp.status_code != 200:
            return cached or []
        data = resp.json()
        metrics = data.get("metrics", {})
        labels = metrics.get("label_list", [])
        _label_list_cache[tenant_id] = labels
        _label_list_ttl[tenant_id] = now + 300
        return labels
    except requests.RequestException:
        return cached or []
