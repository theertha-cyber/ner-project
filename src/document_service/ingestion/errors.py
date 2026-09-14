"""Domain failures of the ingestion operation.

Deliberately not HTTPException. The operation is callable with no HTTP context at all, so
it cannot raise a type that only means something to a web framework; each adapter maps
these to whatever its own protocol says.
"""


class IngestionError(Exception):
    """Base for every rejection the ingestion operation makes."""


class UnsupportedFileType(IngestionError):
    def __init__(self, extension: str):
        self.extension = extension
        super().__init__(f"File type '{extension}' is not supported")


class FileTooLarge(IngestionError):
    def __init__(self, size_bytes: int, limit_bytes: int):
        self.size_bytes = size_bytes
        self.limit_bytes = limit_bytes
        super().__init__(f"File exceeds the {limit_bytes} byte limit ({size_bytes} bytes)")


class IncompatibleRetention(IngestionError):
    """A `single_use` source with `source_only` retention.

    There would be no one to ask for the bytes once the submitting call ends, so the
    document could never be processed. Rejected here rather than discovered by a worker
    that finds nothing to read.
    """

    def __init__(self, acquisition: str, retention_mode: str):
        self.acquisition = acquisition
        self.retention_mode = retention_mode
        super().__init__(
            f"Content declared '{acquisition}' cannot be ingested under "
            f"'{retention_mode}' retention: the bytes cannot be obtained again"
        )


class ReservedSourceId(IngestionError):
    def __init__(self, source_id: str):
        self.source_id = source_id
        super().__init__(f"source_id '{source_id}' is reserved by the platform")
