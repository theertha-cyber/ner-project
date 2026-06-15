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
from sqlalchemy import text, create_engine
from transformers import TrainerCallback

from src.shared.config import settings
from src.shared.auth import create_access_token
from src.training_service.celery_app import celery_app

TRAINING_DEVICE = os.getenv("NER_TRAINING_DEVICE", settings.training_device)
BASE_MODEL = "dslim/bert-base-NER"
ANNOTATION_SERVICE_URL = os.getenv(
    "ANNOTATION_SERVICE_URL",
    "http://annotation_service:8002",
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


def _get_sync_engine():
    return create_engine(settings.database_url_sync)


class TrainingDataError(Exception):
    pass


def tokenize_and_align_labels(
    examples: dict,
    tokenizer,
    label2id: dict,
    max_seq_length: int,
) -> dict:
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
    tokenized["labels"] = labels
    return tokenized


def _load_annotated_dataset(tenant_id: str) -> list[dict]:
    token = _make_service_token(tenant_id)
    resp = requests.get(
        f"{ANNOTATION_SERVICE_URL}/api/v1/annotation-export",
        headers={"Authorization": f"Bearer {token}"},
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


def _update_job_progress(tenant_id: str, job_id: str, **fields):
    engine = _get_sync_engine()
    schema = _schema(tenant_id)
    set_clauses = []
    params = {"id": job_id}
    for key, val in fields.items():
        set_clauses.append(f"{key} = :{key}")
        params[key] = val
    set_sql = ", ".join(set_clauses)
    with engine.begin() as conn:
        conn.execute(
            text(f"UPDATE {schema}.training_jobs SET {set_sql} WHERE id = :id"),
            params,
        )


def _save_artifacts(tenant_id: str, version_id: str, model_dir: str) -> str:
    artifact_path = f"tenants/{tenant_id}/models/v1/{version_id}/"
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
    max_seq_length = hyperparams.get("max_seq_length", 128)

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    experiment_name = f"tenant_{tenant_id}"
    experiment = mlflow.get_experiment_by_name(experiment_name)
    experiment_id = experiment.experiment_id if experiment else mlflow.create_experiment(experiment_name)

    mlflow_run = mlflow.start_run(experiment_id=experiment_id)
    mlflow_run_id = mlflow_run.info.run_id

    try:
        _update_job_progress(
            tenant_id, job_id,
            status="running",
            started_at=datetime.now(timezone.utc),
        )

        records = _load_annotated_dataset(tenant_id)

        label_list = _extract_label_set(records)
        label2id = {lbl: i for i, lbl in enumerate(label_list)}
        id2label = {i: lbl for lbl, i in label2id.items()}

        tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

        dataset = Dataset.from_list(records)
        tokenized_dataset = dataset.map(
            lambda examples: tokenize_and_align_labels(examples, tokenizer, label2id, max_seq_length),
            batched=True,
            remove_columns=dataset.column_names,
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

        split_dataset = tokenized_dataset.train_test_split(test_size=0.1, seed=42)

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
            tokenizer=tokenizer,
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

        metrics = {
            "eval_loss": eval_results.get("eval_loss", 0),
            "eval_precision": eval_results.get("eval_precision", 0),
            "eval_recall": eval_results.get("eval_recall", 0),
            "eval_f1": eval_results.get("eval_f1", 0),
        }

        version_id = str(uuid.uuid4())
        artifact_path = _save_artifacts(tenant_id, version_id, model_dir)

        registered_model_name = f"tenant_{tenant_id}_ner_model"
        mlflow.transformers.log_model(
            transformers_model={"model": model, "tokenizer": tokenizer},
            artifact_path="model",
            registered_model_name=registered_model_name,
        )

        mlflow_run_url = f"{settings.mlflow_tracking_uri}/#/experiments/{experiment_id}/runs/{mlflow_run_id}"
        mlflow.log_param("artifact_path", artifact_path)
        mlflow.log_param("model_version_id", version_id)

        shutil.rmtree(model_dir)
        shutil.rmtree(output_dir)

        engine = _get_sync_engine()
        schema = _schema(tenant_id)
        with engine.begin() as conn:
            conn.execute(
                text(f"""
                    INSERT INTO {schema}.model_versions
                        (id, tenant_id, version_number, training_job_id, status, metrics, artifact_path, created_at, mlflow_run_id)
                    VALUES (:id, :tenant_id,
                        (SELECT COALESCE(MAX(version_number), 0) + 1 FROM {schema}.model_versions WHERE tenant_id = :tenant_id2),
                        :training_job_id, 'completed', CAST(:metrics AS jsonb), :artifact_path, :now, :mlflow_run_id)
                """),
                {
                    "id": version_id,
                    "tenant_id": tenant_id,
                    "tenant_id2": tenant_id,
                    "training_job_id": job_id,
                    "metrics": json.dumps(metrics),
                    "artifact_path": artifact_path,
                    "now": datetime.now(timezone.utc),
                    "mlflow_run_id": mlflow_run_id,
                },
            )

        _update_job_progress(
            tenant_id, job_id,
            status="completed",
            metrics=metrics,
            model_version_id=version_id,
            mlflow_run_id=mlflow_run_id,
            mlflow_run_url=mlflow_run_url,
            completed_at=datetime.now(timezone.utc),
        )

        mlflow.end_run(status="FINISHED")

    except Exception as exc:
        mlflow.set_tag("error_message", str(exc))
        mlflow.end_run(status="FAILED")
        _update_job_progress(
            tenant_id, job_id,
            status="failed",
            error_message=str(exc),
            failed_at=datetime.now(timezone.utc),
        )
        raise
