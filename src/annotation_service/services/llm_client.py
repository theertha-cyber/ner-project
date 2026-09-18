"""The only module in `annotation_service` that knows which LLM provider is configured.

Decision 7 in design.md: grounding and storage sit on the far side of this boundary, so the
provider's failure modes — rate limits, timeouts, output that is not JSON — are handled once,
here, and the deterministic half of the pipeline is testable against `StubLLMClient` without a
network. Nothing outside this module imports a provider SDK.

The provider is Azure OpenAI, using the same settings `extraction_service`'s post-processing
stage already uses (`azure_openai_endpoint`, `azure_openai_api_version`,
`azure_openai_chat_deployment`) with the key read from `openai_api_key`, which has no default in
`Settings` and so can only come from the environment — the AGENTS.md secret-hygiene invariant is
satisfied without introducing a new secret-class setting.
"""

import json
from typing import Protocol

from src.shared.config import settings

# Deterministic output: the same document under the same configuration should not produce a
# different suggestion set on a retry, and the cache (Decision 5) already assumes as much.
LLM_TEMPERATURE = 0
LLM_TIMEOUT_SECONDS = 60.0


class LLMUnavailable(Exception):
    """The provider could not be reached, or returned something unusable.

    Raised rather than swallowed: a pre-labeling job that silently produced zero suggestions
    would be indistinguishable from a document that genuinely contains no entities."""


class LLMClient(Protocol):
    """One call: a system prompt and a user payload in, parsed JSON out."""

    def complete_json(self, system_prompt: str, user_payload: str) -> dict:  # pragma: no cover
        ...


class StubLLMClient:
    """A client that returns a canned response and counts its calls.

    Lives beside the real client rather than in the test tree because the cache tests assert on
    `call_count` and the extraction-scope tests assert on the prompt this received — both are
    properties of the interface, not of any one test."""

    def __init__(self, response: dict | list | None = None):
        self.response = response if response is not None else {"entities": []}
        self.calls: list[tuple[str, str]] = []

    @property
    def call_count(self) -> int:
        return len(self.calls)

    @property
    def last_prompt(self) -> str:
        return self.calls[-1][0] if self.calls else ""

    @property
    def last_payload(self) -> str:
        return self.calls[-1][1] if self.calls else ""

    def complete_json(self, system_prompt: str, user_payload: str) -> dict:
        self.calls.append((system_prompt, user_payload))
        if isinstance(self.response, list):
            return {"entities": self.response}
        return self.response


class AzureOpenAIClient:
    """The configured provider. The SDK import is deferred so importing this module — which the
    API layer does at startup — does not require the provider package to be installed."""

    def complete_json(self, system_prompt: str, user_payload: str) -> dict:
        from openai import APIError, APITimeoutError, AzureOpenAI, OpenAI, RateLimitError

        if settings.azure_openai_endpoint:
            client = AzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                api_key=settings.openai_api_key,
                api_version=settings.azure_openai_api_version,
            )
        else:
            client = OpenAI(api_key=settings.openai_api_key)

        try:
            response = client.chat.completions.create(
                model=settings.azure_openai_chat_deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_payload},
                ],
                response_format={"type": "json_object"},
                temperature=LLM_TEMPERATURE,
                timeout=LLM_TIMEOUT_SECONDS,
            )
        except (RateLimitError, APITimeoutError, APIError) as exc:
            raise LLMUnavailable(f"provider error: {exc}") from exc

        content = response.choices[0].message.content
        try:
            return json.loads(content)
        except (TypeError, json.JSONDecodeError) as exc:
            # Not retried: at temperature 0 the same prompt produces the same shape, so a retry
            # spends tokens to fail again.
            raise LLMUnavailable(f"response was not valid JSON: {exc}") from exc


def get_llm_client() -> LLMClient:
    """The client this deployment is configured to use.

    A deployment that has configured no provider gets `LLMUnavailable` at call time rather than
    a client that quietly returns nothing — pre-labeling is inert where it is not configured,
    and inert has to be visible."""
    return AzureOpenAIClient()
