"""Extraction scope: QA pairs are few-shot context, never a questionnaire.

design.md Decision 3, and the reason it is a hard requirement rather than an optimisation:
`export.py` tags every token not covered by a span as `O`. An entity type left unextracted
because no QA pair mentioned it does not merely go unsuggested — it teaches a future model that
those tokens are not entities. So the prompt must enumerate every active entity type and ask for
every occurrence, whatever the tenant configured.

Covers verification.md rows 4-5. No database and no network: the prompt is built by a pure
function and the provider sits behind `StubLLMClient`.
"""

import pytest

from src.annotation_service.services.llm_client import StubLLMClient
from src.annotation_service.services.llm_prelabel import (
    SYSTEM_PROMPT,
    build_user_payload,
    ground_entities,
    parse_llm_response,
)

INSTITUTE = {
    "name": "institute",
    "description": "An educational institution",
    "examples": ["Vellore Institute of Technology"],
    "qa_examples": [
        {"question": "Which institute did X attend?", "answer": "X attended MIT"},
    ],
}

PERSON_NAME = {
    "name": "person_name",
    "description": "A person's full name",
    "examples": ["John Smith"],
    "qa_examples": [],
}

YEARS_EXPERIENCE = {
    "name": "years_experience",
    "description": "A stated span of professional experience",
    "examples": [],
    "qa_examples": [
        {
            "question": "How many years of experience does X have?",
            "answer": "X has 10 years of experience",
        },
    ],
}


def _run(document_text, entity_types, llm_response):
    """The pipeline minus its I/O: prompt in, grounded spans out."""
    client = StubLLMClient(llm_response)
    payload = build_user_payload(document_text, entity_types)
    response = client.complete_json(SYSTEM_PROMPT, payload)
    entities = parse_llm_response(response)
    result = ground_entities(
        document_text, entities, [entity_type["name"] for entity_type in entity_types]
    )
    return client, payload, result


class TestEntityTypesWithoutQaPairs:
    """verification.md row 4."""

    def test_entity_types_without_qa_pairs_are_extracted(self):
        document_text = (
            "Jane Roe graduated from Vellore Institute of Technology in 2019."
        )
        entity_types = [INSTITUTE, PERSON_NAME]
        _, payload, result = _run(
            document_text,
            entity_types,
            [
                {"entity_type": "institute", "quote": "Vellore Institute of Technology"},
                {"entity_type": "person_name", "quote": "Jane Roe"},
            ],
        )

        stored_types = {span["entity_type"] for span in result.spans}
        assert stored_types == {"institute", "person_name"}

        # The prompt is what makes the above possible rather than lucky: `person_name` has no QA
        # pairs, so a prompt built from the QA pairs alone would never have named it.
        assert "person_name" in payload
        assert "A person's full name" in payload

    def test_prompt_names_every_active_type_even_with_no_examples_or_qa_pairs(self):
        bare = {"name": "job_title", "description": None, "examples": [], "qa_examples": []}
        payload = build_user_payload("some text", [INSTITUTE, bare])
        assert "job_title" in payload


class TestQaPairsDoNotLimitScope:
    """verification.md row 5."""

    def test_qa_pairs_do_not_limit_extraction_scope(self):
        document_text = (
            "Priya has 12 years of experience in data engineering. "
            "Her colleague Sam brings 4 years of experience to the team."
        )
        _, _, result = _run(
            document_text,
            [YEARS_EXPERIENCE],
            [
                {"entity_type": "years_experience", "quote": "12 years of experience"},
                {"entity_type": "years_experience", "quote": "4 years of experience"},
            ],
        )

        # Two mentions, two spans — not one answer to the one configured question.
        assert len(result.spans) == 2
        assert [span["text"] for span in result.spans] == [
            "12 years of experience",
            "4 years of experience",
        ]

    def test_prompt_marks_qa_pairs_as_illustration_not_questions(self):
        payload = build_user_payload("some text", [YEARS_EXPERIENCE])
        assert "for illustration only" in payload
        assert "NOT questions to answer" in payload

    def test_qa_pairs_are_attached_to_their_own_entity_type_only(self):
        """A pair rendered under the wrong type is few-shot context for the wrong thing."""
        payload = build_user_payload("some text", [INSTITUTE, PERSON_NAME])
        institute_block, person_block = payload.split("- person_name")
        assert "Which institute did X attend?" in institute_block
        assert "Which institute did X attend?" not in person_block


@pytest.mark.parametrize(
    "instruction",
    [
        "EVERY occurrence of EVERY entity type",
        "VERBATIM quote",
        "Never invent a new entity type",
        "Do not return character positions",
    ],
)
def test_system_prompt_states_each_binding_instruction(instruction):
    """The four rules the rest of the pipeline assumes the model was told."""
    assert instruction in SYSTEM_PROMPT
