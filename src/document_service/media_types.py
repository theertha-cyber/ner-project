"""What media type a document may be served as, and how a client should render it.

The system decides; the uploader does not. `documents.content_type` is whatever the
uploading client put in its multipart part — it is never validated against the file, and
`is_allowed_file` checks only the filename extension. So a file named `resume.pdf` can
carry a recorded type of `text/html`, and echoing that back would be handing a client a
document the browser is willing to execute.

That matters more here than it would elsewhere. The portal cannot put an Authorization
header on an `<iframe src>`, so it fetches the bytes and renders them from an object URL
— and an object URL inherits the portal's own origin, the origin where the access token
lives in memory. A served `text/html` would run inside it.

So the type is derived from the filename extension, which ingestion *does* validate, and
mapped through a closed allow-list. Anything unrecognised becomes an opaque binary type
that browsers download rather than render. The recorded type is consulted only to
confirm what the extension already said; it can never widen the outcome.

No module in the processing pipeline is imported here: the content routes depend on this,
and the point of the content-resolution extraction was that serving a file should not
construct chunking and the embedding service.
"""

# The only types this platform will serve as themselves, keyed by the extension
# ingestion accepts. Every one is a format a browser either renders inertly or refuses to
# execute. `text/html`, `image/svg+xml` and `application/xhtml+xml` are deliberately
# absent and must never be added: all three are script-bearing.
SERVABLE_TYPES = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".csv": "text/csv",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

# What a client that cannot execute anything is handed when the type is unrecognised.
OPAQUE_TYPE = "application/octet-stream"

# How the viewer should render a document. `convert` means the original is not natively
# renderable and the system will produce a PDF for display; the client still renders a
# PDF, which is what keeps one rendering path in the browser.
RENDER_PDF = "pdf"
RENDER_IMAGE = "image"
RENDER_CONVERT = "convert"
RENDER_DOWNLOAD = "download"

RENDER_MODES = frozenset({RENDER_PDF, RENDER_IMAGE, RENDER_CONVERT, RENDER_DOWNLOAD})

# Browsers render these natively and inertly.
_NATIVE_IMAGE_TYPES = frozenset({"image/jpeg", "image/png"})

# Accepted at upload, renderable by nothing, converted to PDF for display. TIFF is here
# rather than with the images because browsers do not display it.
_CONVERTIBLE_TYPES = frozenset({
    "image/tiff",
    "text/csv",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
})


def _extension(filename: str | None) -> str:
    if not filename:
        return ""
    dot = filename.rfind(".")
    return "" if dot == -1 else filename[dot:].lower()


def servable_media_type(filename: str | None, declared: str | None = None) -> str:
    """The type this document may be served as.

    Derived from the extension, which ingestion validates. `declared` is accepted only so
    a caller need not strip it before calling, and is used solely as a tie-break between
    two types the *extension* already permits — it can never introduce a type the
    extension did not imply. Anything unrecognised is opaque.
    """
    resolved = SERVABLE_TYPES.get(_extension(filename))
    if resolved is None:
        return OPAQUE_TYPE
    # A declared value is honoured only when it agrees with the extension. The `.jpg` /
    # `.jpeg` pair is the only case where agreement is interesting, and even there the
    # answer is identical — so in practice this is a no-op that documents the rule.
    if declared and declared.lower().strip() == resolved:
        return resolved
    return resolved


def render_mode(media_type: str) -> str:
    """How a client should display a document of this served type."""
    if media_type == "application/pdf":
        return RENDER_PDF
    if media_type in _NATIVE_IMAGE_TYPES:
        return RENDER_IMAGE
    if media_type in _CONVERTIBLE_TYPES:
        return RENDER_CONVERT
    return RENDER_DOWNLOAD


def requires_conversion(media_type: str) -> bool:
    return render_mode(media_type) == RENDER_CONVERT
