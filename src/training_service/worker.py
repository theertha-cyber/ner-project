import time
import json
import os
import tempfile
import shutil
import uuid
from datetime import datetime, timezone

import boto3
from botocore.config import Config as BotoConfig
import mlflow
import requests
from sqlalchemy import text
from transformers import TrainerCallback

from src.shared.config import settings
from src.shared.auth import create_access_token
from src.shared.data_plane import DataPlaneNotReady, DataPlaneUnavailable, data_plane_retry_countdown
from src.shared.database import get_resolver
from src.training_service.celery_app import celery_app
from src.training_service.services.consumed_spans import (
    dataset_span_ids,
    record_consumed_spans,
)
from src.shared.observability.domain_metrics import (
    record_training_completion,
    record_training_failure,
    record_training_transition,
)

TRAINING_DEVICE = os.getenv("NER_TRAINING_DEVICE", settings.training_device)
BASE_MODEL = "dslim/bert-base-NER"

# Sequence length. This is derived from the annotation export's window budget, not
# chosen independently — export emits records of at most WINDOW_TOKENS source tokens
# (`src/annotation_service/api/v1/export.py`), and this default must be large enough
# that such a record's subword expansion fits without truncation.
#
#   export window budget                          128 source tokens
#   measured subword expansion (this corpus)      mean 1.99, max 3.64 per source token
#   worst-case subwords for a full window         128 * 3.64 + 2 specials = 468
#   BERT positional-embedding hard cap            512
#
# 512 is therefore the smallest standard value that clears the measured worst case (it
# allows (512 - 2) / 128 = 3.98 subwords per source token) while staying inside the
# model's own limit. Changing either constant requires re-deriving the other.
EXPORT_WINDOW_TOKENS = 128
MODEL_MAX_POSITIONS = 512
DEFAULT_MAX_SEQ_LENGTH = MODEL_MAX_POSITIONS

# Fraction of the dataset held out for evaluation, and the source of the split guard's
# arithmetic. It is not a data-sufficiency threshold: per-entity-type dataset readiness
# is owned by NER_MIN_ENTITIES_PER_TYPE (ADR-010) and is untouched here.
EVAL_SPLIT_FRACTION = 0.1
ANNOTATION_SERVICE_URL = os.getenv(
    "ANNOTATION_SERVICE_URL",
    "http://annotation_service:8000",
)


class MLflowCallback(TrainerCallback):
    def __init__(self, experiment_name: str, run_id: str):
        self.experiment_name = experiment_name
        self.run_id = run_id

    def on_log(self, args, state, control, logs=None, **kwargs):
        if not logs:
            return
        metrics = {}
        for key, val in logs.items():
            if isinstance(val, (int, float)):
                metrics[key] = val
        if metrics:
            mlflow.log_metrics(metrics, step=state.global_step)


def _schema(tenant_id: str) -> str:
    return f"tenant_{tenant_id.replace('-', '_')}"


def _make_service_token(tenant_id: str) -> str:
    return create_access_token(
        tenant_id=tenant_id,
        user_id="training-worker",
        role="system_admin",
    )


def _get_sync_engine(tenant_id: str):
    """The one place this worker obtains a tenant-schema engine — routed through
    `EngineResolver` (ADR-017). Never construct an engine from
    `settings.database_url_sync` for tenant-schema access anywhere else in this file."""
    return get_resolver().resolve_sync(tenant_id)


class TrainingDataError(Exception):
    pass


def tokenize_and_align_labels(
    examples: dict,
    tokenizer,
    label2id: dict,
    max_seq_length: int,
    truncation_stats: dict | None = None,
) -> dict:
    """Tokenise a batch and align BIO tags to subwords.

    When `truncation_stats` is supplied, records whose subword expansion overflows
    `max_seq_length` are counted into it. Truncation still happens — the job must not
    fail because of it — but it stops being invisible: a record that loses its tail
    also loses every annotation in that tail, and that has to be reportable.
    """
    tokenized = tokenizer(
        examples["tokens"],
        is_split_into_words=True,
        truncation=True,
        padding="max_length",
        max_length=max_seq_length,
    )
    labels = []
    for i, tags in enumerate(examples["tags"]):
        word_ids = tokenized.word_ids(batch_index=i)
        label_ids = []
        for word_idx in word_ids:
            if word_idx is None:
                label_ids.append(-100)
            else:
                label_ids.append(label2id.get(tags[word_idx], 0))
        labels.append(label_ids)

        if truncation_stats is not None and tags:
            covered = {w for w in word_ids if w is not None}
            dropped = len(tags) - len(covered)
            if dropped > 0:
                truncation_stats["records"] = truncation_stats.get("records", 0) + 1
                truncation_stats["dropped_tokens"] = (
                    truncation_stats.get("dropped_tokens", 0) + dropped
                )

    tokenized["labels"] = labels
    return tokenized


def _assert_dataset_splittable(row_count: int, test_size: float = EVAL_SPLIT_FRACTION) -> None:
    """Fail the job when no train/evaluation split with at least one evaluation row exists.

    Deliberately mechanical. It answers only "can this dataset be split at all?" — it
    makes no judgement about whether the data is enough to train a *good* model, which
    is ADR-010's per-entity-type readiness threshold and not this guard's business.
    """
    import math

    eval_rows = math.ceil(row_count * test_size)
    train_rows = row_count - eval_rows
    if eval_rows < 1 or train_rows < 1:
        raise TrainingDataError(
            f"Dataset has {row_count} row(s), which cannot form a train/evaluation split "
            f"at test_size={test_size} with at least one evaluation row "
            f"(would give {train_rows} train / {eval_rows} evaluation). "
            "Annotate more documents before training."
        )


def _load_annotated_dataset(tenant_id: str, source_scope: str | None = None) -> list[dict]:
    token = _make_service_token(tenant_id)
    params = {"source": source_scope} if source_scope else {}
    resp = requests.get(
        f"{ANNOTATION_SERVICE_URL}/api/v1/annotation-export",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    if not resp.text.strip():
        raise TrainingDataError("No annotated data found for tenant")

    lines = resp.text.strip().split("\n")
    records = []
    for line in lines:
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def _extract_label_set(records: list[dict]) -> list[str]:
    labels = set()
    for r in records:
        for tag in r["tags"]:
            if tag != "O":
                labels.add(tag)
    sorted_labels = sorted(labels)
    return ["O"] + sorted_labels


def _training_failure_cause(exc: BaseException) -> str:
    """Map a raised exception onto the enumerated failure causes.

    Deliberately coarse. The alternative — inferring a cause from the message text — would
    put the exception's words one string operation away from a metric label, and a
    training failure message routinely quotes a path, a dataset row or a tenant identifier.
    Anything not confidently classifiable is `training_error`, and the specific class is on
    the span and in the log record where it can be read safely.
    """
    name = type(exc).__name__
    if name in ("TimeoutError", "SoftTimeLimitExceeded"):
        return "timeout"
    if name in ("KeyboardInterrupt", "CancelledError"):
        return "cancelled"
    if name in ("FileNotFoundError", "NoCredentialsError", "ClientError", "EndpointConnectionError"):
        return "export_error"
    return "training_error"


def _update_job_progress(tenant_id: str, job_id: str, **fields):
    """Write job fields, and count a state transition when the status is one of them.

    Counted here rather than at each caller: this is the single funnel every status write
    passes through, and ADR-009 makes the `training_jobs` row the authority on a job's
    identity and state. A counter at each caller would be a convention the next author has
    to remember; a counter here cannot be bypassed without bypassing the write itself.
    """
    status = fields.get("status")
    if status is not None:
        record_training_transition(str(status))

    engine = _get_sync_engine(tenant_id)
    schema = _schema(tenant_id)
    set_clauses = []
    params = {"id": job_id}
    for key, val in fields.items():
        if isinstance(val, dict):
            val = json.dumps(val)
        set_clauses.append(f"{key} = :{key}")
        params[key] = val
    set_sql = ", ".join(set_clauses)
    with engine.begin() as conn:
        conn.execute(
            text(f"UPDATE {schema}.training_jobs SET {set_sql} WHERE id = :id"),
            params,
        )


def _save_artifacts(tenant_id: str, version_number: int, model_dir: str) -> str:
    artifact_path = f"tenants/{tenant_id}/models/v{version_number}/"
    s3 = boto3.client(
        "s3",
        endpoint_url=f"http://{settings.minio_endpoint}",
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=BotoConfig(signature_version="s3v4"),
    )
    bucket = settings.minio_bucket

    try:
        s3.head_bucket(Bucket=bucket)
    except Exception:
        s3.create_bucket(Bucket=bucket)

    for root, dirs, files in os.walk(model_dir):
        for fname in files:
            file_path = os.path.join(root, fname)
            object_name = os.path.join(artifact_path, fname)
            s3.upload_file(file_path, bucket, object_name)
    return artifact_path


@celery_app.task(bind=True, name="fine_tune_model", max_retries=0)
def fine_tune_model(self, tenant_id: str, job_id: str, hyperparams: dict):
    import torch
    from transformers import (
        AutoTokenizer,
        AutoModelForTokenClassification,
        TrainingArguments,
        Trainer,
        DataCollatorForTokenClassification,
    )
    from datasets import Dataset

    learning_rate = hyperparams.get("learning_rate", 2e-5)
    num_epochs = hyperparams.get("num_epochs", 3)
    batch_size = hyperparams.get("batch_size", 8)
    # Still sourced from the job's approved hyperparameters (ADR-009); only the
    # fallback default moved.
    max_seq_length = hyperparams.get("max_seq_length", DEFAULT_MAX_SEQ_LENGTH)

    try:
        engine = _get_sync_engine(tenant_id)
    except (DataPlaneUnavailable, DataPlaneNotReady) as exc:
        if self.request.retries < settings.data_plane_task_max_retries:
            raise self.retry(
                exc=exc,
                countdown=data_plane_retry_countdown(self.request.retries),
                max_retries=settings.data_plane_task_max_retries,
            )
        return {"job_id": job_id, "status": "failed_retryable", "reason": "data_plane_unavailable"}
    schema = _schema(tenant_id)
    source_scope: str | None = None
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(f"SELECT status, source_scope FROM {schema}.training_jobs WHERE id = :id"),
                {"id": job_id},
            ).fetchone()
            if row is not None:
                status = row[0]
                source_scope = row[1]
                if status in ("completed", "failed", "cancelled"):
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning("Job %s already %s, skipping", job_id, status)
                    return
            elif row is None:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning("Job %s not found in database, skipping", job_id)
                return
    except Exception as exc:
        # A failure here (e.g. a stale pooled connection) happens before the job
        # is ever marked "running" — nothing downstream will touch its status, so
        # without this it stays stuck at "queued" forever instead of surfacing
        # as a failure.
        record_training_failure(_training_failure_cause(exc))
        _update_job_progress(
            tenant_id, job_id,
            status="failed",
            error_message=str(exc),
            failed_at=datetime.now(timezone.utc),
        )
        raise

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    experiment_name = f"tenant_{tenant_id}"
    experiment = mlflow.get_experiment_by_name(experiment_name)
    experiment_id = experiment.experiment_id if experiment else mlflow.create_experiment(experiment_name)

    mlflow_run = mlflow.start_run(experiment_id=experiment_id)
    mlflow_run_id = mlflow_run.info.run_id
    job_started = time.monotonic()

    try:
        _update_job_progress(
            tenant_id, job_id,
            status="running",
            started_at=datetime.now(timezone.utc),
        )

        records = _load_annotated_dataset(tenant_id, source_scope=source_scope)

        # Captured here, alongside the export it describes, and held until completion. The
        # spans this run trains on are the ones that existed when the export was taken; a
        # reviewer confirming a span while the run executes has produced evidence this model
        # never saw, and re-querying at completion would record it as trained on anyway
        # (design.md Decision 1). Nothing is written yet — a job that fails from here on
        # consumed nothing.
        with engine.connect() as conn:
            consumed_span_ids = dataset_span_ids(conn, schema)

        # Before anything expensive, and before anything that could report a metric.
        _assert_dataset_splittable(len(records))

        label_list = _extract_label_set(records)
        label2id = {lbl: i for i, lbl in enumerate(label_list)}
        id2label = {i: lbl for lbl, i in label2id.items()}

        tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

        dataset = Dataset.from_list(records)
        truncation_stats: dict = {}
        tokenized_dataset = dataset.map(
            lambda examples: tokenize_and_align_labels(
                examples, tokenizer, label2id, max_seq_length, truncation_stats
            ),
            batched=True,
            remove_columns=dataset.column_names,
        )

        truncated_records = truncation_stats.get("records", 0)
        if truncated_records:
            import logging
            logging.getLogger(__name__).warning(
                "Truncation at max_seq_length=%s affected %s of %s record(s), "
                "dropping %s source token(s) and any annotations within them",
                max_seq_length,
                truncated_records,
                len(records),
                truncation_stats.get("dropped_tokens", 0),
            )

        model = AutoModelForTokenClassification.from_pretrained(
            BASE_MODEL,
            num_labels=len(label_list),
            id2label=id2label,
            label2id=label2id,
            ignore_mismatched_sizes=True,
        )

        mlflow.log_params({
            "learning_rate": learning_rate,
            "num_epochs": num_epochs,
            "batch_size": batch_size,
            "max_seq_length": max_seq_length,
        })
        mlflow.log_metrics({
            "dataset_rows": len(records),
            "truncated_records": truncated_records,
            "truncated_source_tokens": truncation_stats.get("dropped_tokens", 0),
        })
        mlflow.set_tags({
            "base_model": BASE_MODEL,
            "tenant_id": tenant_id,
            "training_job_id": job_id,
            "num_labels": len(label_list),
        })

        data_collator = DataCollatorForTokenClassification(tokenizer)

        output_dir = tempfile.mkdtemp()
        training_args = TrainingArguments(
            output_dir=output_dir,
            learning_rate=learning_rate,
            per_device_train_batch_size=batch_size,
            num_train_epochs=num_epochs,
            eval_strategy="epoch",
            save_strategy="epoch",
            logging_strategy="epoch",
            save_total_limit=2,
            load_best_model_at_end=True,
            metric_for_best_model="eval_loss",
            remove_unused_columns=False,
            dataloader_pin_memory=False,
            use_cpu=(TRAINING_DEVICE == "cpu"),
        )

        split_dataset = tokenized_dataset.train_test_split(test_size=EVAL_SPLIT_FRACTION, seed=42)

        def compute_metrics(eval_pred):
            from evaluate import load as load_metric
            metric = load_metric("seqeval")
            predictions, labels = eval_pred
            predictions = predictions.argmax(axis=-1)
            true_labels = []
            true_preds = []
            for pred_seq, label_seq in zip(predictions, labels):
                lbls = []
                prds = []
                for p, l in zip(pred_seq, label_seq):
                    if l != -100:
                        lbls.append(id2label[l])
                        prds.append(id2label[p])
                true_labels.append(lbls)
                true_preds.append(prds)
            results = metric.compute(predictions=true_preds, references=true_labels)
            per_entity_metrics = {}
            for entity_type, scores in results.items():
                if isinstance(scores, dict):
                    for metric_name, val in scores.items():
                        per_entity_metrics[f"{entity_type}_{metric_name}"] = val
            return {
                "eval_loss": float(eval_pred.losses.mean()) if hasattr(eval_pred, "losses") and eval_pred.losses is not None else 0,
                "eval_precision": results.get("overall_precision", 0),
                "eval_recall": results.get("overall_recall", 0),
                "eval_f1": results.get("overall_f1", 0),
                **per_entity_metrics,
            }

        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=split_dataset["train"],
            eval_dataset=split_dataset["test"],
            data_collator=data_collator,
            compute_metrics=compute_metrics,
            callbacks=[MLflowCallback(experiment_name, mlflow_run_id)],
        )

        trainer.train()
        eval_results = trainer.evaluate()

        mlflow.log_metrics({
            "eval_loss": eval_results.get("eval_loss", 0),
            "eval_precision": eval_results.get("eval_precision", 0),
            "eval_recall": eval_results.get("eval_recall", 0),
            "eval_f1": eval_results.get("eval_f1", 0),
        })
        for key, val in eval_results.items():
            if key.startswith("eval_") and isinstance(val, (int, float)) and key not in ("eval_loss", "eval_precision", "eval_recall", "eval_f1"):
                mlflow.log_metric(key, val)

        model_dir = tempfile.mkdtemp()
        trainer.save_model(model_dir)
        tokenizer.save_pretrained(model_dir)

        onnx_model = trainer.model
        onnx_model.eval()
        dummy_inputs = tokenizer(
            "dummy input text for onnx export tracing",
            return_tensors="pt",
            padding="max_length",
            truncation=True,
            max_length=max_seq_length,
        )
        onnx_path = os.path.join(model_dir, "model.onnx")
        torch.onnx.export(
            onnx_model,
            (dummy_inputs["input_ids"], dummy_inputs["attention_mask"]),
            onnx_path,
            input_names=["input_ids", "attention_mask"],
            output_names=["logits"],
            dynamic_axes={
                "input_ids": {0: "batch", 1: "sequence"},
                "attention_mask": {0: "batch", 1: "sequence"},
                "logits": {0: "batch", 1: "sequence"},
            },
            opset_version=14,
            # torch>=2.9 defaults to the dynamo exporter, which requires the
            # onnxscript package; dynamic_axes needs the legacy exporter.
            dynamo=False,
        )

        metrics = {
            "eval_loss": eval_results.get("eval_loss", 0),
            "eval_precision": eval_results.get("eval_precision", 0),
            "eval_recall": eval_results.get("eval_recall", 0),
            "eval_f1": eval_results.get("eval_f1", 0),
            "label_list": label_list,
            "dataset_rows": len(records),
            "truncated_records": truncated_records,
            "truncated_source_tokens": truncation_stats.get("dropped_tokens", 0),
        }

        with engine.connect() as conn:
            row = conn.execute(
                text(f"SELECT COALESCE(MAX(version_number), 0) + 1 FROM {schema}.model_versions WHERE tenant_id = :tenant_id"),
                {"tenant_id": tenant_id},
            ).fetchone()
            version_number = row[0]
            job_run_number_row = conn.execute(
                text(f"SELECT run_number FROM {schema}.training_jobs WHERE tenant_id = :tenant_id AND id = :job_id"),
                {"tenant_id": tenant_id, "job_id": job_id},
            ).fetchone()
            run_number = job_run_number_row[0] if job_run_number_row else None

        version_id = str(uuid.uuid4())
        artifact_path = _save_artifacts(tenant_id, version_number, model_dir)

        registered_model_name = f"tenant_{tenant_id}_ner_model"
        mlflow.transformers.log_model(
            transformers_model={"model": model, "tokenizer": tokenizer},
            artifact_path="model",
            registered_model_name=registered_model_name,
            pip_requirements=["torch"],
        )

        mlflow_run_url = f"{settings.mlflow_tracking_uri}/#/experiments/{experiment_id}/runs/{mlflow_run_id}"
        mlflow.log_param("artifact_path", artifact_path)
        mlflow.log_param("model_version_id", version_id)
        mlflow.log_param("label_list", json.dumps(label_list))

        shutil.rmtree(model_dir)
        shutil.rmtree(output_dir)

        engine = _get_sync_engine(tenant_id)
        schema = _schema(tenant_id)
        with engine.begin() as conn:
            conn.execute(
                text(f"""
                    INSERT INTO {schema}.model_versions
                        (id, tenant_id, version_number, training_job_id, status, metrics, artifact_path, created_at, mlflow_run_id, run_number)
                    VALUES (:id, :tenant_id, :version_number,
                        :training_job_id, 'training', CAST(:metrics AS jsonb), :artifact_path, :now, :mlflow_run_id, :run_number)
                """),
                {
                    "id": version_id,
                    "tenant_id": tenant_id,
                    "version_number": version_number,
                    "training_job_id": job_id,
                    "metrics": json.dumps(metrics),
                    "artifact_path": artifact_path,
                    "now": datetime.now(timezone.utc),
                    "mlflow_run_id": mlflow_run_id,
                    "run_number": run_number,
                },
            )

        _update_job_progress(
            tenant_id, job_id,
            status="completed",
            metrics=json.dumps(metrics),
            model_version_id=version_id,
            mlflow_run_id=mlflow_run_id,
            mlflow_run_url=mlflow_run_url,
            completed_at=datetime.now(timezone.utc),
        )

        with engine.begin() as conn:
            conn.execute(
                text(f"UPDATE {schema}.model_versions SET status = 'completed' WHERE id = :id AND tenant_id = :tenant_id"),
                {"id": version_id, "tenant_id": tenant_id},
            )
            # The run succeeded and produced `version_number`, so — and only so — the spans it
            # trained on stop being accumulation. Same transaction as the status flip: a record
            # written without the version reaching `completed`, or the reverse, would leave
            # accumulation describing a run that does not exist in the state it describes.
            #
            # This is the whole of what completion does beyond recording its own result. It
            # starts no follow-on run and it promotes nothing — version_number sits in
            # `completed` until a person promotes it (design.md Decision 3).
            record_consumed_spans(
                conn,
                schema,
                consumed_span_ids,
                model_version=version_number,
                training_job_id=job_id,
            )

        mlflow.end_run(status="FINISHED")
        # Lifecycle only. F1, precision, recall and loss are logged to MLflow above and
        # are deliberately not mirrored here: MLflow versions them against the run, the
        # params and the artifact, and a Prometheus copy would be a second source of truth
        # with worse fidelity, no run linkage and a retention window that disagrees.
        # "Is the job stuck" is an operational question; "is this model good" is not.
        # See design Decision 9.
        record_training_completion(
            "completed", time.monotonic() - job_started, epochs=num_epochs
        )

    except Exception as exc:
        record_training_failure(_training_failure_cause(exc))
        record_training_completion("failed", time.monotonic() - job_started)
        mlflow.set_tag("error_message", str(exc))
        mlflow.end_run(status="FAILED")
        _update_job_progress(
            tenant_id, job_id,
            status="failed",
            error_message=str(exc),
            failed_at=datetime.now(timezone.utc),
        )
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(f"UPDATE {schema}.model_versions SET status = 'failed' WHERE id = :id AND tenant_id = :tenant_id"),
                    {"id": version_id, "tenant_id": tenant_id},
                )
        except Exception:
            pass
        raise
