"""The three declared retention modes.

Its own module, with no imports, because both the ingestion contract and the processing
worker need these names and importing one from the other would close a cycle. The same
three values are constrained in the database by migration 038.
"""

# The original is written to the durable content store and retained. Bytes are reopened
# from that store for the life of the document.
RETENTION_PLATFORM_BLOB = "platform_blob"

# The original is written to a working content store under a bounded lifetime, used to
# complete processing, and deleted at a terminal state. No durable original is retained.
#
# Stated rather than hidden: under this mode the bytes *do* transit platform-operated
# storage for the duration of processing. "No retention" means no durable original, not
# "the bytes never touch our infrastructure".
RETENTION_EPHEMERAL = "ephemeral"

# No bytes are written to any platform store; they are reopened by asking the originating
# source adapter. Modelled now, executable when pull sources land.
RETENTION_SOURCE_ONLY = "source_only"

RETENTION_MODES = frozenset(
    {RETENTION_PLATFORM_BLOB, RETENTION_EPHEMERAL, RETENTION_SOURCE_ONLY}
)
