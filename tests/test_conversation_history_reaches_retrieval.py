"""A follow-up question often carries its subject only in the earlier turns
("which of the following candidates …"). Retrieval is what has to honour that, and
retrieval runs behind two layers that used to drop the history: the planner sliced a
different window than the one configured, and the structured tool handed its SQL
generator a hardcoded `None` in place of the conversation. Either one alone is enough
to turn a follow-up into a fresh tenant-wide search that answers a different question,
so both paths are pinned here.
"""

import pytest

from src.shared.config import settings
from src.shared.conversation_history import recent_messages, render_history
from src.shared.retrieval.orchestrator import _build_messages
from src.shared.retrieval.tools.base import ToolContext
from src.shared.retrieval.tools.entity_tools import structured_retrieval

pytestmark = pytest.mark.asyncio

HISTORY = [
    {"role": "user", "content": "fetch me the names of candidates who know python"},
    {"role": "assistant", "content": "Mahalakshmi S, Hannah, Harshith Akshayraj R.S"},
]
FOLLOW_UP = "which of the following candidates would be a strong fit for an AI engineer role?"


class TestSharedWindow:
    def test_window_is_the_configured_one(self):
        history = [{"role": "user", "content": str(i)} for i in range(20)]
        assert len(recent_messages(history)) == settings.conversation_history_turns

    def test_absent_history_renders_as_none_not_empty_string(self):
        assert render_history(None) is None
        assert render_history([]) is None

    def test_rendering_keeps_role_and_order(self):
        assert render_history(HISTORY) == (
            "user: fetch me the names of candidates who know python\n"
            "assistant: Mahalakshmi S, Hannah, Harshith Akshayraj R.S"
        )


class TestPlannerSeesTheReferent:
    def test_prior_turns_precede_the_follow_up(self):
        messages = _build_messages(FOLLOW_UP, HISTORY)

        assert messages[0]["role"] == "system"
        assert [m["content"] for m in messages[1:]] == [
            HISTORY[0]["content"], HISTORY[1]["content"], FOLLOW_UP,
        ]

    def test_planner_window_matches_every_other_stage(self):
        """The planner used to keep its own 3-message window while prompt assembly
        used the configured one, so the two stages could disagree about which turns
        exist — the planner scoping retrieval from turns the answer never saw."""
        history = [{"role": "user", "content": str(i)} for i in range(20)]
        planner_history = _build_messages("q", history)[1:-1]

        assert planner_history == recent_messages(history)

    def test_planner_is_told_to_resolve_references_into_arguments(self):
        """A capability receives its `arguments` and nothing else. If the system
        prompt does not say so, the planner passes 'which of the following
        candidates' straight through and retrieval searches the whole tenant."""
        system_prompt = _build_messages("q", None)[0]["content"]

        assert "only the arguments you give it" in system_prompt


class TestStructuredToolSeesTheReferent:
    async def test_history_reaches_sql_generation(self):
        seen = {}

        async def sql_search(query, session, schema, conversation_context, **_kwargs):
            seen["conversation_context"] = conversation_context
            return []

        context = ToolContext(
            tenant_id="tenant-1", schema="tenant_test", session=object(),
            sql_search=sql_search, conversation_context=HISTORY,
        )

        await structured_retrieval.call({"query": FOLLOW_UP}, context)

        assert seen["conversation_context"] == HISTORY
