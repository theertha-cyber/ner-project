"""Verification for uploader-scope threading — verification.md rows 17-19, 52-53.

The rule is enforced in SQL by the retrievers. What this file pins is that the requesting
user actually *reaches* them: identically on the JSON and streaming routes, independently
per concurrent request, and as the explicit no-end-user value on the widget path.

The failure mode being guarded is not a wrong predicate — it is a correct predicate that
nothing ever supplies a user to, which fails closed and quietly empties every answer.
"""

import asyncio
import inspect

import pytest

from src.chat_api.api.v1 import chat as chat_routes
from src.chat_api.api.v1 import public as public_routes
from src.chat_api.services.rag_orchestrator import RAGOrchestrator
from src.shared.document_visibility import NO_REQUESTING_USER, RequestingUser

pytestmark = [pytest.mark.verification]


class _FakeState:
    def __init__(self, user_id=None, role=None):
        self.user_id = user_id
        self.role = role


class _FakeRequest:
    def __init__(self, user_id=None, role=None):
        self.state = _FakeState(user_id, role)


# --- Row 52: both routes build the same requesting user ----------------------------


def test_requesting_user_is_built_from_authenticated_request_state():
    user = chat_routes._requesting_user(_FakeRequest("recruiter-1", "business_user"))
    assert user == RequestingUser(user_id="recruiter-1", role="business_user")


def test_requesting_user_survives_missing_state_without_becoming_unscoped():
    """An unauthenticated or half-populated request must not produce an admin."""
    user = chat_routes._requesting_user(_FakeRequest())
    assert user.user_id is None
    assert user.is_unscoped is False


def test_both_routes_pass_the_requesting_user():
    """Row 52. The streaming route is a separate call site and is the one that gets
    forgotten; asserting on the source keeps them from drifting."""
    source = inspect.getsource(chat_routes)
    assert source.count("requesting_user=_requesting_user(request)") == 2, (
        "both the JSON and the streaming chat route must pass the requesting user"
    )


@pytest.mark.parametrize(
    "method",
    ["execute", "execute_with_clarification", "execute_with_clarification_stream"],
)
def test_every_orchestrator_entry_point_accepts_a_requesting_user(method):
    params = inspect.signature(getattr(RAGOrchestrator, method)).parameters
    assert "requesting_user" in params


def test_graph_state_carries_the_requesting_user():
    source = inspect.getsource(RAGOrchestrator._run_graph)
    assert '"requesting_user": requesting_user' in source


def test_tool_context_receives_it_from_graph_state():
    from src.chat_api.graph import nodes

    source = inspect.getsource(nodes)
    assert 'requesting_user=state.get("requesting_user")' in source


# --- Row 53: no request-scoped identity on the shared instance ----------------------


def test_orchestrator_holds_no_requesting_user_attribute():
    """Row 53's second clause. The orchestrator is a module-level singleton shared by
    every concurrent request; an identity stored on it would leak across users."""
    orchestrator = RAGOrchestrator.__new__(RAGOrchestrator)
    assert not hasattr(orchestrator, "requesting_user")
    assert "self.requesting_user" not in inspect.getsource(RAGOrchestrator)


async def test_interleaved_requests_each_carry_their_own_user():
    """Row 53. Two turns running concurrently in one process must reach the graph with
    different users — the property that a shared attribute would destroy."""
    captured = []

    class _CapturingOrchestrator(RAGOrchestrator):
        def __init__(self):  # no LLM clients needed
            pass

        async def _run_graph(self, message, session, schema, tenant_id, jwt_token=None,
                             conversation_context=None, conversation_id=None,
                             token_sink=None, requesting_user=None):
            # Yield control between capture points so the two calls genuinely interleave.
            await asyncio.sleep(0)
            captured.append((message, requesting_user))
            await asyncio.sleep(0)
            return {"reply": "ok", "sources": []}

    orchestrator = _CapturingOrchestrator()
    await asyncio.gather(
        orchestrator.execute(
            "a", None, "s", "t",
            requesting_user=RequestingUser(user_id="user-a", role="business_user"),
        ),
        orchestrator.execute(
            "b", None, "s", "t",
            requesting_user=RequestingUser(user_id="user-b", role="business_user"),
        ),
    )

    by_message = dict(captured)
    assert by_message["a"].user_id == "user-a"
    assert by_message["b"].user_id == "user-b"


# --- Rows 17-19: the widget has no end user ----------------------------------------


def test_widget_passes_the_explicit_no_end_user_value():
    """Rows 17-18. The widget must not inherit a default that happens to be right; the
    absence of an identity is the decision, and it is made at the call site."""
    source = inspect.getsource(public_routes)
    assert "requesting_user=NO_REQUESTING_USER" in source


def test_no_end_user_admits_source_system_content_only():
    """Row 19 at the value level: the widget's scope excludes every human upload."""
    from src.shared.document_visibility import visibility_predicate

    predicate, params = visibility_predicate(NO_REQUESTING_USER)
    assert predicate == "ingested_by_kind <> 'human'"
    assert params == {}


def test_no_end_user_is_not_an_administrator():
    assert NO_REQUESTING_USER.is_unscoped is False
