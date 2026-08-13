"""Answer-level evaluation — verification.md rows 85, 86, 87.

Chunk-ranking metrics say whether retrieval put the right passage near the top. They
say nothing about whether the turn ANSWERED the question, which is what the
investigation found failing in 10 of 10 traced queries while the ranking metrics looked
healthy. Each case here names a question and the facts the reply must contain, and
passes only when the produced reply contains them.

The harness is deliberately deterministic: the pipeline's reply is supplied by the
caller, so a case fails for a missing fact rather than for a flaky model.
"""

from dataclasses import dataclass, field

import pytest

pytestmark = [pytest.mark.verification]


# Phrases a reply uses to claim it found nothing. A case whose required fact exists in
# the tenant's data must fail when the reply says this, however fluent the sentence.
ABSENCE_CLAIMS = (
    "couldn't find",
    "could not find",
    "no information",
    "not available",
    "does not appear",
    "doesn't appear",
    "no matching",
    "nothing in your data",
    "isn't in the",
    "is not in the",
)


@dataclass
class AnswerCase:
    """One answer-level case. `required_facts` are the substrings the reply must
    contain, compared case-insensitively — the facts, not the phrasing."""

    case_id: str
    question: str
    required_facts: list[str]
    query_class: str | None = None
    # Set when the facts are known to exist in the corpus, so a reply asserting absence
    # is a false negative rather than an honest one.
    facts_exist: bool = True


@dataclass
class AnswerCaseResult:
    case_id: str
    passed: bool
    missing_facts: list[str] = field(default_factory=list)
    false_absence_claim: bool = False

    @property
    def report(self) -> str:
        if self.passed:
            return f"{self.case_id}: pass"
        parts = []
        if self.false_absence_claim:
            parts.append("reply claimed the information was unavailable, but it exists in the data")
        if self.missing_facts:
            parts.append("missing required fact(s): " + ", ".join(self.missing_facts))
        return f"{self.case_id}: fail — " + "; ".join(parts)


def evaluate_answer(case: AnswerCase, reply: str) -> AnswerCaseResult:
    lowered = (reply or "").lower()
    missing = [f for f in case.required_facts if f.lower() not in lowered]
    false_absence = case.facts_exist and any(claim in lowered for claim in ABSENCE_CLAIMS)
    return AnswerCaseResult(
        case_id=case.case_id,
        passed=not missing and not false_absence,
        missing_facts=missing,
        false_absence_claim=false_absence,
    )


# The cases the investigation's traces map onto. Kept beside the harness so a class
# that stops being covered is visible in one place.
ANSWER_CASES = [
    AnswerCase(
        case_id="email-lookup",
        question="What is Mahalakshmi's email address?",
        required_facts=["mahalakshmi.s@example.com"],
        query_class="exact_entity_lookup",
    ),
    AnswerCase(
        case_id="skill-enumeration",
        question="Which tools does Arjun know?",
        required_facts=["aws", "docker"],
        query_class="simple_structured",
    ),
    AnswerCase(
        case_id="two-subject-comparison",
        question="Compare Hannah and Girish.",
        required_facts=["hannah", "girish"],
        query_class="multi_document",
    ),
]


class TestAnswerLevelHarness:
    def test_case_passes_when_all_required_facts_present(self):
        case = ANSWER_CASES[0]
        result = evaluate_answer(case, "Mahalakshmi's email address is mahalakshmi.s@example.com.")

        assert result.passed
        assert result.missing_facts == []
        assert "pass" in result.report

    def test_case_fails_and_names_omitted_fact(self):
        case = ANSWER_CASES[1]
        result = evaluate_answer(case, "Arjun knows AWS.")

        assert not result.passed
        assert result.missing_facts == ["docker"]
        assert "docker" in result.report

    def test_false_absence_claim_fails_the_case(self):
        """The single most damaging failure the investigation found: a broken turn
        reporting that the tenant's data does not contain what it plainly does."""
        case = ANSWER_CASES[0]
        result = evaluate_answer(
            case, "I couldn't find relevant information to answer that question.",
        )

        assert not result.passed
        assert result.false_absence_claim
        assert "exists in the data" in result.report

    def test_honest_absence_is_not_penalised(self):
        case = AnswerCase(
            case_id="genuinely-absent", question="Who knows COBOL?",
            required_facts=[], facts_exist=False,
        )
        result = evaluate_answer(case, "I couldn't find any candidate who knows COBOL.")

        assert result.passed

    def test_matching_is_case_insensitive_on_facts_not_phrasing(self):
        case = AnswerCase(case_id="c", question="q", required_facts=["AWS"])
        assert evaluate_answer(case, "They know aws and Docker.").passed

    def test_every_case_names_a_question_and_its_required_facts(self):
        for case in ANSWER_CASES:
            assert case.question.strip()
            assert case.required_facts
            assert case.query_class
