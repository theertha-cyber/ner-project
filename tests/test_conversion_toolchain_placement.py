"""The conversion toolchain lives only where conversion happens.

Covers "Only the converting service carries the toolchain".

Every Python service in this platform builds from one Dockerfile. LibreOffice is several
hundred megabytes, and adding it to the shared runtime stage would put it in the
model-serving, training, annotation and extraction images for a capability none of them
use. That is the kind of regression nobody notices until a deploy is slow, so it is
asserted rather than trusted to review.
"""

import re
from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.verification]

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")

CONVERTING_TARGET = "runtime-documents"
TOOLCHAIN_MARKERS = ("libreoffice", "soffice")


def _stages() -> dict[str, str]:
    """Each build stage's instructions, keyed by its name.

    Comments are dropped: this guard is about what a stage *installs*, and the block
    explaining why the toolchain is confined to one stage necessarily names it. Matching
    prose would make the guard fire on its own documentation.
    """
    stages: dict[str, str] = {}
    current = None
    for raw in DOCKERFILE.splitlines():
        line = raw.split("#", 1)[0] if raw.lstrip().startswith("#") else raw
        match = re.match(r"^FROM\s+\S+(?:\s+AS\s+(\S+))?", line, re.IGNORECASE)
        if match:
            current = match.group(1) or "<unnamed>"
            stages[current] = ""
            continue
        if current:
            stages[current] += line + "\n"
    return stages


def test_the_converting_stage_carries_the_toolchain():
    stages = _stages()
    assert CONVERTING_TARGET in stages, "the document-service build target is missing"
    body = stages[CONVERTING_TARGET].lower()
    assert any(marker in body for marker in TOOLCHAIN_MARKERS)


def test_no_other_stage_carries_the_toolchain():
    offenders = [
        name
        for name, body in _stages().items()
        if name != CONVERTING_TARGET
        and any(marker in body.lower() for marker in TOOLCHAIN_MARKERS)
    ]
    assert offenders == [], (
        f"the conversion toolchain leaked into {offenders}; every Python service builds "
        "from this Dockerfile and would carry it"
    )


def test_only_the_document_service_builds_from_the_converting_target():
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    using = [
        name
        for name, service in (compose.get("services") or {}).items()
        if isinstance(service.get("build"), dict)
        and service["build"].get("target") == CONVERTING_TARGET
    ]
    assert using == ["document_service"], f"unexpected services on the converting target: {using}"


def test_the_converting_stage_extends_the_shared_runtime():
    """It must inherit tesseract, poppler and the installed packages rather than
    reinstalling them — otherwise the two images drift."""
    assert re.search(
        rf"^FROM\s+runtime\s+AS\s+{CONVERTING_TARGET}\s*$",
        DOCKERFILE,
        re.IGNORECASE | re.MULTILINE,
    )
