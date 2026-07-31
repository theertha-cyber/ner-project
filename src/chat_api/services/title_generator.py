import re

_PLACEHOLDER_TITLE = "New conversation"
_MAX_TITLE_LENGTH = 60
_STRIP_CHARS = " \t\n\r.,;:!?\"'`~"


def derive_conversation_title(message: str) -> str:
    collapsed = re.sub(r"\s+", " ", message).strip(_STRIP_CHARS)
    if not collapsed:
        return _PLACEHOLDER_TITLE

    if len(collapsed) <= _MAX_TITLE_LENGTH:
        return collapsed

    truncated = collapsed[:_MAX_TITLE_LENGTH]
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]
    truncated = truncated.rstrip(_STRIP_CHARS)
    return truncated + "…" if truncated else _PLACEHOLDER_TITLE
