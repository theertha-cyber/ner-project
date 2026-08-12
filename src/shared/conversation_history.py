"""Single definition of how much prior conversation each LLM call sees, and how it
is rendered when a call takes text rather than a message list.

Every stage that consults history — the domain classifier, the retrieval planner, SQL
generation, and final prompt assembly — previously sliced the message list itself, and
three of them hardcoded a different window than the one `conversation_history_turns`
configures. A follow-up whose referent ("the following candidates") sits in an earlier
turn is answered correctly only if every stage sees the same turns, so the window lives
here and each stage calls through it.

`conversation_context` is a flat list of `{"role", "content"}` message dicts, not
turn pairs: the window bounds *messages*, so N admits roughly N/2 user/assistant
exchanges.
"""

from src.shared.config import settings


def recent_messages(conversation_context: list[dict] | None, limit: int | None = None) -> list[dict]:
    """The trailing window of history, oldest first. Empty list when there is none."""
    if not conversation_context:
        return []
    window = limit if limit is not None else settings.conversation_history_turns
    if window <= 0:
        return []
    return conversation_context[-window:]


def render_history(conversation_context: list[dict] | None, limit: int | None = None) -> str | None:
    """The same window rendered as `role: content` lines, for the prompts that
    interpolate history as text instead of appending it as chat messages. `None`
    (not an empty string) when there is no history, so callers can test it directly."""
    messages = recent_messages(conversation_context, limit)
    if not messages:
        return None
    return "\n".join(f"{m['role']}: {m['content']}" for m in messages)
