import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.verification

SRC_ROOT = Path(__file__).resolve().parent.parent / "src"


def _python_files():
    return list(SRC_ROOT.rglob("*.py"))


def test_exactly_one_system_prompt_definition():
    """Covers scenario 14: task 6.3."""
    pattern = re.compile(r"^SYSTEM_PROMPT\s*=", re.MULTILINE)
    matches = []
    for path in _python_files():
        content = path.read_text(encoding="utf-8")
        if pattern.search(content):
            matches.append(str(path))
    assert matches == [str(SRC_ROOT / "chat_api" / "services" / "context_assembler.py")]


def test_no_character_slice_of_chunk_text():
    """Covers Hallucination Risk 1: task 6.4."""
    pattern = re.compile(r"chunk_text\[:\d+\]|chunk_str\[:\d+\]")
    offenders = []
    for path in _python_files():
        content = path.read_text(encoding="utf-8")
        if pattern.search(content):
            offenders.append(str(path))
    assert offenders == []
