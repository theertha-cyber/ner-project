import os
import logging
import numpy as np
import onnxruntime as ort
from transformers import AutoTokenizer, pipeline
from src.model_serving.services.model_cache import model_cache
from src.model_serving.services.model_loader import download_model_artifacts, estimate_model_memory
from src.shared.config import settings

logger = logging.getLogger(__name__)

BASE_MODEL = "dslim/bert-base-NER"
CONLL_LABELS = ["O", "B-PER", "I-PER", "B-ORG", "I-ORG", "B-LOC", "I-LOC", "B-MISC", "I-MISC"]
_tokenizer = None
_base_pipeline = None


def _get_tokenizer():
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    return _tokenizer


def _get_base_pipeline():
    global _base_pipeline
    if _base_pipeline is None:
        _base_pipeline = pipeline("ner", model=BASE_MODEL, tokenizer=BASE_MODEL)
    return _base_pipeline


def _resolve_active_version(tenant_id: str) -> tuple[str, int]:
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
            return "base", 0
        data = resp.json()
        return data["artifact_path"], data["version_number"]
    except requests.RequestException:
        return "base", 0


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


def _infer_with_onnx(tokens: list[str], tenant_id: str) -> list[dict]:
    session = None
    version_info = _resolve_active_version(tenant_id)
    artifact_path, version_number = version_info
    model_id = f"{tenant_id}_v{version_number}"

    cached = model_cache.get(model_id)
    if cached is not None:
        session = cached.model["session"]
    else:
        loaded = _load_model_for_tenant(tenant_id, version_number)
        if loaded:
            cached = model_cache.get(model_id)
            if cached is not None:
                session = cached.model["session"]

    if session is None:
        return _infer_with_base_model(tokens)

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

    label_list = _resolve_label_list(tenant_id)
    if not label_list:
        label_list = CONLL_LABELS

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


def _infer_with_base_model(tokens: str | list[str]) -> list[dict]:
    pipe = _get_base_pipeline()
    text = " ".join(tokens) if isinstance(tokens, list) else tokens
    raw = pipe(text)
    grouped = {}
    for item in raw:
        word = item["word"]
        label = item["entity"]
        score = item["score"]
        if word not in grouped or score > grouped[word]["confidence"]:
            grouped[word] = {"token": word, "label": label, "confidence": score}
    return list(grouped.values())


def infer(tenant_id: str, tokens: list[str]) -> tuple[list[dict], str] | tuple[None, None]:
    artifact_path, version_number = _resolve_active_version(tenant_id)

    if artifact_path == "base":
        predictions = _infer_with_base_model(tokens)
        return predictions, "0"

    try:
        predictions = _infer_with_onnx(tokens, tenant_id)
        return predictions, str(version_number)
    except Exception as exc:
        logger.warning("Fine-tuned model inference failed for tenant=%s version=%d: %s. Falling back to base model.", tenant_id, version_number, exc)
        predictions = _infer_with_base_model(tokens)
        return predictions, "0"


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
            return cached or CONLL_LABELS
        data = resp.json()
        metrics = data.get("metrics", {})
        labels = metrics.get("label_list", [])
        if not labels:
            return CONLL_LABELS
        _label_list_cache[tenant_id] = labels
        _label_list_ttl[tenant_id] = now + 300
        return labels
    except requests.RequestException:
        return cached or CONLL_LABELS
