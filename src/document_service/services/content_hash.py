import hashlib

CONTENT_HASH_ALGORITHM = "sha256"


def compute_content_hash(data: bytes) -> str:
    """Deterministic content identity for an uploaded document: the lowercase
    SHA-256 hex digest of the raw file bytes. Depends only on the bytes, never on
    filename, upload time, uploader, purpose, or document id, so the same physical
    document uploaded under any name always hashes the same. 64 hex characters,
    matching the `documents.checksum VARCHAR(64)` column."""
    return hashlib.sha256(data).hexdigest()
