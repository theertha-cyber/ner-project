"""Guards the generation prompt's identity-and-evidence directive.

A logged "fetch me candidates who know Python" turn came back with rows carrying only
`document_name` and the matched skill. The answering model, given no name column, read
names out of the filenames ("Resume - Hannah.pdf") and wrote "Unnamed Candidate" for the
files that held none — presenting a filename guess as though it were retrieved data, and
merging two different people who had both uploaded a "Resume.pdf".

The relational surface changes how a name is retrieved — it is a `subject` column or its own
relation, not a second self-join of the EAV store — but it changes none of the failure modes
these tests pin: evidence crowded out by identity columns, a filename passed off as a name, and
identity columns dragged into a GROUP BY.

Only the prompt is asserted on. Whether the LLM obeys it is not something a test can settle;
what it can settle is that the instruction is present, mandatory, and names what the result
needs.
"""

from types import SimpleNamespace

import pytest

from src.chat_api.services.sql_generator import SQLGenerator
from src.shared.entity_views import EntityDefinitionSpec, build_query_surface

pytestmark = [pytest.mark.verification, pytest.mark.asyncio]

CANDIDATE_QUERY = "fetch me candidates who know python"

SURFACE = build_query_surface([
    EntityDefinitionSpec(name="Skill", sql_identifier="e_skill"),
    EntityDefinitionSpec(name="Name", sql_identifier="e_name", cardinality="single"),
])


class PromptCapturingLLM:
    """Captures the generation prompt and returns a fixed statement."""

    def __init__(self, response: str = "SELECT 1"):
        self.response = response
        self.prompts: list[str] = []
        self.chat = SimpleNamespace(completions=self)

    async def create(self, **kwargs):
        self.prompts.append(kwargs["messages"][0]["content"])
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.response))]
        )


async def _prompt_for(query: str = CANDIDATE_QUERY) -> str:
    generator = SQLGenerator()
    llm = PromptCapturingLLM()
    generator.client = llm
    await generator.generate_sql(query, surface=SURFACE)
    return llm.prompts[0]


class TestIdentityDirective:
    async def test_prompt_requires_document_id_on_every_row(self):
        """The identity that survives filename collisions, and the only column the graph's
        scope filter and citation assembly can key on."""
        prompt = await _prompt_for()

        assert "MUST project `document_id`" in prompt
        assert "cannot be cited or scoped" in prompt

    async def test_prompt_asks_for_the_subjects_name_where_the_tenant_has_one(self):
        """The observed failure: no name column, so the answering model read names out of
        filenames. On the relational surface the name is a listed relation or column."""
        prompt = await _prompt_for()

        assert "relation or column holding subjects' names" in prompt
        assert "Reshma U" in prompt

    async def test_prompt_forbids_passing_a_filename_off_as_a_name(self):
        prompt = await _prompt_for()

        assert "`subject.filename` is never the subject's name" in prompt
        assert "select it, never filter on it" in prompt

    async def test_prompt_does_not_teach_the_old_eav_name_join(self):
        """The second `document_entities` join is gone: `subject` carries the filename and the
        name column directly, so a query that self-joins the entity store would be rejected by
        the validation layer as well as pointless."""
        prompt = await _prompt_for()

        assert "LEFT JOIN document_entities" not in prompt
        assert "candidate_name" not in prompt
        assert "entity_type" not in prompt

    async def test_directive_is_not_scoped_to_one_phrasing(self):
        """The guidance is part of the standing prompt, so it reaches every structured query
        rather than only the "who knows X" wording."""
        prompts = [
            await _prompt_for("who has the most years of experience"),
            await _prompt_for("list everyone with a B.Tech"),
            await _prompt_for("show me each candidate's email"),
        ]

        for prompt in prompts:
            assert "MUST project `document_id`" in prompt
            assert "**The matched fact itself**" in prompt

    async def test_aggregates_remain_exempt(self):
        """Forcing extra columns into a GROUP BY would split the groups and break every
        ranking query, so the carve-out has to survive alongside the directive."""
        prompt = await _prompt_for()

        assert "An aggregate grouped by `document_id` satisfies both" in prompt


class TestEvidenceColumnSurvivesTheIdentityColumns:
    """The regression the first version of this directive caused.

    Asked for candidates who know Python, the model returned document_id, filename and a name
    — and no Python. The answering model, holding four names and no trace of what they matched
    on, correctly reported that it could not determine their skills. The identity columns had
    crowded out the evidence they were meant to accompany.
    """

    async def test_prompt_demands_the_matched_fact_as_its_own_column(self):
        prompt = await _prompt_for()

        assert "**The matched fact itself**" in prompt
        assert "projected as a named column" in prompt

    async def test_prompt_ranks_evidence_before_identity(self):
        """Ordering is the fix: the evidence requirement has to be read first, since the
        failure was the identity block being taken for the whole projection."""
        prompt = await _prompt_for()

        assert prompt.index("**The matched fact itself**") < prompt.index(
            "**Who the row is about**"
        )

    async def test_prompt_states_the_consequence_of_dropping_the_evidence(self):
        """Naming the concrete failure, not just the rule — the model has to know what
        breaks, because 'four names and no Python' looks like a plausible answer."""
        prompt = await _prompt_for()

        assert "cannot answer \"who knows Python\"" in prompt
        assert "alongside the evidence, never instead of it" in prompt
