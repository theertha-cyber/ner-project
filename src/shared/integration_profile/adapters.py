"""The declared set of adapter selections, and which of them are executable.

A profile may *record* any value from the supported set. Only the platform defaults can
be activated or can serve a request. The presence of a recordable value is not a claim
that the adapter exists — that separation is what lets a profile express the target
architecture without implying any of it works yet.
"""

# --- Adapter kinds, per selection slot -------------------------------------------------

SOURCE_ADAPTERS = frozenset({"platform_upload", "keka", "s3", "azure_blob", "sharepoint"})
CONTENT_STORE_ADAPTERS = frozenset({"platform_minio", "tenant_s3", "tenant_azure_blob"})
RELATIONAL_ADAPTERS = frozenset({"platform_postgresql", "tenant_postgresql"})
INDEX_ADAPTERS = frozenset({"platform_pgvector", "tenant_pgvector", "external_index"})

# --- The platform defaults: the only executable selections in this change --------------

DEFAULT_SOURCE_ADAPTER = "platform_upload"
DEFAULT_CONTENT_STORE_ADAPTER = "platform_minio"
DEFAULT_RELATIONAL_ADAPTER = "platform_postgresql"
DEFAULT_INDEX_ADAPTER = "platform_pgvector"

EXECUTABLE_ADAPTERS = {
    "source_adapter": DEFAULT_SOURCE_ADAPTER,
    "content_store_adapter": DEFAULT_CONTENT_STORE_ADAPTER,
    "relational_adapter": DEFAULT_RELATIONAL_ADAPTER,
    "index_adapter": DEFAULT_INDEX_ADAPTER,
}

SUPPORTED_ADAPTERS = {
    "source_adapter": SOURCE_ADAPTERS,
    "content_store_adapter": CONTENT_STORE_ADAPTERS,
    "relational_adapter": RELATIONAL_ADAPTERS,
    "index_adapter": INDEX_ADAPTERS,
}


def unsupported_selections(selections: dict) -> list[str]:
    """Names of the slots whose recorded selection is not executable in this change."""
    return sorted(
        slot
        for slot, executable in EXECUTABLE_ADAPTERS.items()
        if selections.get(slot) not in (None, executable)
    )
