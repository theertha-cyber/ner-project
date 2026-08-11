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

# Hard ceiling of the BERT positional embedding table. A sequence longer than this
# cannot be fed to the ONNX graph at all, so it is the absolute bound that
# settings.inference_window_size (+ 2 special tokens) must respect.
MODEL_MAX_POSITIONS = 512
NUM_SPECIAL_TOKENS = 2  # [CLS] ... [SEP]

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
    registry_url = f"{settings.training_service_url.rstrip('/')}/api/v1/models/active"
    try:
        resp = requests.get(
            registry_url,
            headers={"Authorization": f"Bearer {token}"},
            params={"tenant_id": tenant_id},
            timeout=10,
        )
        if resp.status_code != 200:
            return "base", 0
        data = resp.json()
        return data["artifact_path"], data["version_number"]
    except requests.RequestException:
        return "base", 0


def _load_model_for_tenant(tenant_id: str, version_number: int, artifact_path: str) -> bool:
    model_id = f"{tenant_id}_v{version_number}"
    cached = model_cache.get(model_id)
    if cached is not None:
        return True

    local_dir = download_model_artifacts(tenant_id, version_number, artifact_path)
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


def _window_geometry() -> tuple[int, int]:
    """Resolves (window_budget, overlap) in WordPiece units, clamped so that
    window_budget + NUM_SPECIAL_TOKENS never exceeds MODEL_MAX_POSITIONS and the
    overlap always leaves forward progress."""
    budget = min(settings.inference_window_size, MODEL_MAX_POSITIONS - NUM_SPECIAL_TOKENS)
    budget = max(budget, 1)
    overlap = max(0, min(settings.inference_window_overlap, budget - 1))
    return budget, overlap


def _wordpiece_counts(tokenizer, tokens: list[str]) -> list[int]:
    """WordPiece length of each whitespace word, in word order. Uses one
    `is_split_into_words` encoding with truncation disabled so the counts describe
    the *whole* input — this is the measurement that used to be skipped entirely,
    letting `truncation=True` drop the tail of every long document in silence.

    A count of 0 means the tokenizer has no WordPiece for that word at all — PDF
    extraction routinely yields private-use-area glyphs such as U+F0B7 (a bullet)
    that normalize away to nothing. Such a word is unlabelable, not truncated.

    `verbose=False` suppresses transformers' "sequence longer than the maximum"
    notice: exceeding 512 here is the whole point of the measurement, and the model
    is never actually fed this encoding."""
    encoding = tokenizer(
        tokens,
        is_split_into_words=True,
        truncation=False,
        add_special_tokens=False,
        verbose=False,
    )
    counts = [0] * len(tokens)
    for word_id in encoding.word_ids(0):
        if word_id is not None:
            counts[word_id] += 1
    return counts


def _build_windows(piece_counts: list[int], budget: int, overlap: int) -> list[tuple[int, int]]:
    """Partitions word indices into overlapping `[start, end)` windows, each fitting
    `budget` WordPieces. Windows are expressed in *word* indices so that a word is
    never split across two windows — that is what keeps every prediction mappable
    back to exactly one entry of the caller's token list.

    A single word longer than the whole budget still gets its own window (and is
    reported by the caller) rather than silently derailing the walk."""
    windows: list[tuple[int, int]] = []
    n = len(piece_counts)
    start = 0
    while start < n:
        used = 0
        end = start
        while end < n:
            if end > start and used + piece_counts[end] > budget:
                break
            used += piece_counts[end]
            end += 1
        windows.append((start, end))
        if end >= n:
            break
        # Step back over `overlap` WordPieces so the next window re-reads the tail
        # of this one with full right-hand context. `start + 1` floor guarantees
        # forward progress even when one word alone fills the budget.
        new_start = end
        recovered = 0
        while new_start > start + 1 and recovered < overlap:
            new_start -= 1
            recovered += piece_counts[new_start]
        start = new_start
    return windows


def _infer_window(
    session,
    tokenizer,
    window_tokens: list[str],
    label_list: list[str],
    max_length: int,
) -> list[tuple[int, str, float]]:
    """Runs one window through the ONNX graph. Returns
    `[(local_word_index, label, confidence)]` for **every** word the model saw,
    including `O` — the caller needs the `O` predictions to decide overlap
    conflicts, and drops them only after a winner is picked."""
    encoding = tokenizer(
        window_tokens,
        is_split_into_words=True,
        truncation=True,
        max_length=max_length,
        padding=True,
        return_tensors="np",
    )

    input_ids = encoding["input_ids"].astype(np.int64)
    attention_mask = encoding["attention_mask"].astype(np.int64)
    token_type_ids = encoding.get("token_type_ids", None)

    session_input_names = {inp.name for inp in session.get_inputs()}
    inputs = {"input_ids": input_ids, "attention_mask": attention_mask}
    if token_type_ids is not None and "token_type_ids" in session_input_names:
        inputs["token_type_ids"] = token_type_ids.astype(np.int64)

    outputs = session.run(None, inputs)
    logits = outputs[0]
    predicted_ids = logits.argmax(axis=-1)[0]
    scores = np.max(logits, axis=-1)[0]
    word_ids = encoding.word_ids(0)

    results: list[tuple[int, str, float]] = []
    seen_words = set()
    for word_id, pred_id, prob in zip(word_ids, predicted_ids, scores):
        if word_id is None or word_id in seen_words:
            continue
        seen_words.add(word_id)
        if pred_id == 0:
            label = "O"
        else:
            label = label_list[pred_id] if pred_id < len(label_list) else f"LABEL_{pred_id}"
        results.append((int(word_id), label, float(prob)))

    return results


def _infer_with_onnx(tokens: list[str], tenant_id: str) -> list[dict]:
    session = None
    version_info = _resolve_active_version(tenant_id)
    artifact_path, version_number = version_info
    model_id = f"{tenant_id}_v{version_number}"

    cached = model_cache.get(model_id)
    if cached is not None:
        session = cached.model["session"]
    else:
        loaded = _load_model_for_tenant(tenant_id, version_number, artifact_path)
        if loaded:
            cached = model_cache.get(model_id)
            if cached is not None:
                session = cached.model["session"]

    if session is None:
        return _infer_with_base_model(tokens)

    tokenizer = _get_tokenizer()

    label_list = _resolve_label_list(tenant_id)
    if not label_list:
        label_list = CONLL_LABELS

    budget, overlap = _window_geometry()
    piece_counts = _wordpiece_counts(tokenizer, tokens)
    windows = _build_windows(piece_counts, budget, overlap)

    oversized = [i for i, c in enumerate(piece_counts) if c > budget]
    if oversized:
        logger.warning(
            "Inference input for tenant=%s contains %d word(s) longer than the "
            "%d-WordPiece window budget; these words are truncated inside their own "
            "window. First offenders (word_index, wordpieces): %s",
            tenant_id,
            len(oversized),
            budget,
            [(i, piece_counts[i]) for i in oversized[:5]],
        )

    # word index -> (distance from nearest window edge, confidence, label).
    # Overlap regions get a prediction from two windows; the one whose word sat
    # further from a window edge wins, because edge tokens are labelled with
    # truncated context and their BIO tags are the unreliable ones. Confidence
    # breaks exact ties.
    best: dict[int, tuple[int, float, str]] = {}

    for win_start, win_end in windows:
        window_tokens = tokens[win_start:win_end]
        window_preds = _infer_window(
            session, tokenizer, window_tokens, label_list, budget + NUM_SPECIAL_TOKENS
        )
        for local_id, label, confidence in window_preds:
            global_id = win_start + local_id
            distance = min(global_id - win_start, (win_end - 1) - global_id)
            candidate = (distance, confidence, label)
            incumbent = best.get(global_id)
            if incumbent is None or candidate[:2] > incumbent[:2]:
                best[global_id] = candidate

    # Coverage is checked against the words the tokenizer can actually represent.
    # Anything representable that no window labelled is real, silent data loss —
    # exactly the failure mode this windowing replaced — so it is reported loudly.
    representable = {i for i, count in enumerate(piece_counts) if count > 0}
    missing = sorted(representable - best.keys())
    if missing:
        logger.warning(
            "Sliding-window inference for tenant=%s labelled only %d/%d representable "
            "words across %d window(s) (budget=%d). Entities in the %d unlabelled "
            "word(s) are missing; first indices: %s",
            tenant_id, len(representable) - len(missing), len(representable),
            len(windows), budget, len(missing), missing[:10],
        )

    unrepresentable = len(tokens) - len(representable)
    if unrepresentable:
        logger.info(
            "Inference input for tenant=%s contains %d word(s) with no WordPiece "
            "representation (e.g. private-use PDF glyphs); nothing to label there.",
            tenant_id, unrepresentable,
        )

    results = []
    for global_id in sorted(best):
        _, confidence, label = best[global_id]
        if label == "O":
            continue
        results.append({
            "token": tokens[global_id],
            "label": label,
            "confidence": confidence,
            # Index into the caller's own token list. Lets the extraction worker map
            # a prediction back to its character offset exactly, instead of scanning
            # forward for matching token text.
            "word_index": global_id,
        })

    return results


def _infer_with_base_model(tokens: str | list[str]) -> list[dict]:
    """Returns one prediction per model output token, in source order, with no
    deduplication by word text — downstream BIO reconstruction depends on both
    order and repeated occurrences of the same word."""
    pipe = _get_base_pipeline()
    text = " ".join(tokens) if isinstance(tokens, list) else tokens
    word_count = len(tokens) if isinstance(tokens, list) else len(text.split())
    if word_count > MODEL_MAX_POSITIONS - NUM_SPECIAL_TOKENS:
        logger.warning(
            "Base-model fallback received %d words, which may exceed the %d-position "
            "limit of %s. The base path is unwindowed; predictions past the limit "
            "may be missing.",
            word_count, MODEL_MAX_POSITIONS, BASE_MODEL,
        )
    raw = pipe(text)
    return [
        {"token": item["word"], "label": item["entity"], "confidence": float(item["score"])}
        for item in raw
    ]


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
    registry_url = f"{settings.training_service_url.rstrip('/')}/api/v1/models/active"
    try:
        resp = requests.get(
            registry_url,
            headers={"Authorization": f"Bearer {token}"},
            params={"tenant_id": tenant_id},
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
