"""A stable fingerprint of a tenant's active entity-type configuration.

LLM pre-labeling caches its results on (document content hash, entity-config version): a tenant
that adds a QA pair or a new entity type must not keep being served suggestions produced under
the old configuration. This module produces that version.

It is a content hash rather than a counter for two reasons. Entity types carry their own
per-row `version`, but a tenant's configuration is the *set* of them — adding a type bumps no
existing row's version, and deactivating one bumps nothing at all, so no per-row counter can
stand in for the whole. And a hash needs no extra column, no write path, and no backfill: it is
derived from what the catalog already holds, so it cannot fall out of step with it.

The fields hashed are every field that changes what a pre-labeling run actually does: what the
external prompt asks for and how few-shot examples are worded (`name`, `description`, `examples`,
`qa_examples`), and — since `automated-annotation-pii-masking` — what governs local-only
detection instead of an external call (`sensitivity`, `validation_rule`, `base_label_mapping`).
A tenant who reclassifies a type, tightens a `pattern` regex, or edits a `local_only` type's
base-label mapping has changed what this pipeline produces, even though nothing about the
document itself changed, and a stale cache entry would silently keep serving the old behavior.
`updated_at` and `version` are deliberately excluded: an edit that changes neither the prompt,
the local-detection inputs, nor the eligible type set should not throw away a valid cache entry.
"""

import hashlib
import json

from sqlalchemy import text

# Ordered so the SELECT, the fingerprint, and prompt construction all agree on what "the
# configuration" is, and adding a field to one cannot silently omit it from the others.
CONFIG_FIELDS = (
    "name", "description", "examples", "qa_examples",
    "sensitivity", "validation_rule", "base_label_mapping",
)

_SELECT_ACTIVE = (
    "SELECT name, description, examples, qa_examples, sensitivity, validation_rule, "
    "       base_label_mapping "
    "FROM public.entity_definitions "
    "WHERE tenant_id = :tid AND is_active = true "
    "ORDER BY name"
)


def _coerce_json(value):
    """A JSON column reads back as a parsed value on some drivers and as text on others.

    Normalized here so the same configuration cannot fingerprint two different ways depending
    on which driver loaded it — which would make the cache miss on every alternate call."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def normalize_entity_config(rows) -> list[dict]:
    """Configuration rows as plain, ordered dicts ready to hash or render into a prompt."""
    normalized = []
    for row in rows:
        name, description, examples, qa_examples, sensitivity, validation_rule, base_label_mapping = (
            row[0], row[1], row[2], row[3], row[4], row[5], row[6],
        )
        normalized.append(
            {
                "name": name,
                "description": description,
                "examples": _coerce_json(examples) or [],
                "qa_examples": _coerce_json(qa_examples) or [],
                "sensitivity": sensitivity or "open",
                "validation_rule": validation_rule,
                "base_label_mapping": _coerce_json(base_label_mapping) or {},
            }
        )
    normalized.sort(key=lambda item: item["name"])
    return normalized


def entity_config_fingerprint(entity_types: list[dict]) -> str:
    """A stable hex digest over the given configuration.

    `sort_keys=True` and the caller's name ordering together mean two loads of the same
    configuration produce the same digest regardless of row order or dict insertion order."""
    payload = json.dumps(
        [{field: item.get(field) for field in CONFIG_FIELDS} for item in entity_types],
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def load_active_entity_config(session, tenant_id: str) -> list[dict]:
    result = await session.execute(text(_SELECT_ACTIVE), {"tid": tenant_id})
    return normalize_entity_config(result.fetchall())


def load_active_entity_config_sync(connection, tenant_id: str) -> list[dict]:
    """The same read for the Celery worker, which runs on a synchronous engine."""
    result = connection.execute(text(_SELECT_ACTIVE), {"tid": tenant_id})
    return normalize_entity_config(result.fetchall())


async def entity_config_version(session, tenant_id: str) -> str:
    return entity_config_fingerprint(await load_active_entity_config(session, tenant_id))


def entity_config_version_sync(connection, tenant_id: str) -> str:
    return entity_config_fingerprint(load_active_entity_config_sync(connection, tenant_id))
