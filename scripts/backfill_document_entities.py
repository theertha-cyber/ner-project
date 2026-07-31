"""Backfill `document_entities` for documents extracted before normalized entity
storage existed.

Existing `extracted_entities` rows carry no ordering column and no offsets, so BIO
sequences cannot be reliably reconstructed from them (see design.md Decision 8).
This script re-runs inference for each affected document instead, and writes only
to `document_entities` — `extracted_entities` is never modified.

Idempotent: re-running for an already-backfilled document replaces (delete +
insert) its `document_entities` rows rather than duplicating them.

Run:
    python scripts/backfill_document_entities.py --tenant <tenant_id> [--dry-run]
"""
import argparse
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from sqlalchemy import create_engine, text

from src.extraction_service.services.document_entity_store import delete_document_entities, insert_document_entities
from src.extraction_service.services.entity_normalizer import merge_wordpieces, reconstruct_entities
from src.extraction_service.worker import _align_predictions_with_offsets, _tokenize_span
from src.shared.auth import create_access_token
from src.shared.config import settings


def _schema(tenant_id: str) -> str:
    return f"tenant_{tenant_id.replace('-', '_')}"


def _documents_needing_backfill(conn, schema: str) -> list[str]:
    result = conn.execute(
        text(f"""
            SELECT DISTINCT e.document_id
            FROM {schema}.extracted_entities e
            LEFT JOIN {schema}.document_entities d ON d.document_id = e.document_id
            WHERE d.document_id IS NULL
        """)
    )
    return [row[0] for row in result.fetchall()]


def _fetch_token_records(conn, schema: str, document_id: str) -> list[dict]:
    result = conn.execute(
        text(f"""
            SELECT text, page_number, char_start FROM {schema}.document_text_spans
            WHERE document_id = :doc_id
            ORDER BY span_index NULLS LAST
        """),
        {"doc_id": document_id},
    )
    token_records = []
    for span_text, page_number, span_char_start in result.fetchall():
        if not span_text:
            continue
        token_records.extend(_tokenize_span(span_text, page_number, span_char_start))
    return token_records


def backfill_document(conn, schema: str, tenant_id: str, document_id: str, dry_run: bool) -> bool:
    token_records = _fetch_token_records(conn, schema, document_id)
    tokens = [t["token"] for t in token_records]
    if not tokens:
        return False

    if dry_run:
        return True

    serving_token = create_access_token(tenant_id=tenant_id, user_id="backfill-script", role="system_admin")
    infer_url = f"{settings.model_serving_url}/internal/v1/infer"
    resp = requests.post(
        infer_url,
        headers={"Authorization": f"Bearer {serving_token}"},
        json={"tokens": tokens},
        timeout=60,
    )
    if resp.status_code == 404:
        return False
    resp.raise_for_status()
    predictions = resp.json().get("predictions", [])

    aligned = _align_predictions_with_offsets(predictions, token_records)
    merged = merge_wordpieces(aligned)
    entities = reconstruct_entities(merged)

    delete_document_entities(conn, schema, document_id)
    insert_document_entities(conn, schema, document_id, entities)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", required=True, help="Tenant id to backfill")
    parser.add_argument("--dry-run", action="store_true", help="Report affected document counts without writing")
    args = parser.parse_args()

    schema = _schema(args.tenant)
    engine = create_engine(settings.database_url_sync)

    with engine.connect() as conn:
        doc_ids = _documents_needing_backfill(conn, schema)

    print(f"{len(doc_ids)} document(s) need backfill for tenant '{args.tenant}'.")
    if args.dry_run:
        for doc_id in doc_ids:
            print(f"  [dry-run] would backfill {doc_id}")
        return

    backfilled = 0
    skipped = 0
    for doc_id in doc_ids:
        with engine.begin() as conn:
            ok = backfill_document(conn, schema, args.tenant, doc_id, dry_run=False)
        if ok:
            backfilled += 1
            print(f"  [backfilled] {doc_id}")
        else:
            skipped += 1
            print(f"  [skipped] {doc_id} (no tokens or no model available)")

    print(f"Done. {backfilled} backfilled, {skipped} skipped.")


if __name__ == "__main__":
    main()
