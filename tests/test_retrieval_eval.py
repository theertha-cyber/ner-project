import json
import os

import pytest

from src.shared.retrieval.eval.embeddings import EmbeddingModelMismatchError, PrecomputedEmbeddingService
from src.shared.retrieval.eval.golden_set import GoldenSetError, load_corpus, load_golden_set

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "retrieval_eval")
CORPUS_PATH = os.path.join(FIXTURES_DIR, "corpus.jsonl")
GOLDEN_SET_PATH = os.path.join(FIXTURES_DIR, "golden_set.jsonl")
EMBEDDINGS_PATH = os.path.join(FIXTURES_DIR, "embeddings.json")


class TestGoldenSetLoads:
    """Covers verification.md row 23."""

    def test_golden_set_loads_and_validates(self):
        corpus = load_corpus(CORPUS_PATH)
        queries = load_golden_set(GOLDEN_SET_PATH, corpus)

        assert len(queries) >= 30
        for q in queries:
            assert q.query_id
            assert q.query
            assert isinstance(q.relevant, list)
            for j in q.relevant:
                assert j.document_id
                assert isinstance(j.chunk_index, int)
                assert 0 <= j.grade <= 3


class TestDuplicateQueryIdRejected:
    """Covers verification.md row 24."""

    def test_duplicate_query_id_rejected(self, tmp_path):
        p = tmp_path / "dupes.jsonl"
        p.write_text(
            json.dumps({"query_id": "q1", "query": "a", "relevant": []}) + "\n" +
            json.dumps({"query_id": "q1", "query": "b", "relevant": []}) + "\n",
            encoding="utf-8",
        )
        with pytest.raises(GoldenSetError, match="q1"):
            load_golden_set(str(p))


class TestJudgmentsResolveAgainstCorpus:
    """Covers verification.md row 25."""

    def test_judgments_resolve_against_corpus(self):
        corpus = load_corpus(CORPUS_PATH)
        # load_golden_set with corpus= raises if any judgment doesn't resolve;
        # a clean load is itself the proof for the committed fixtures.
        load_golden_set(GOLDEN_SET_PATH, corpus)

    def test_unresolvable_judgment_rejected(self, tmp_path):
        corpus = [type("C", (), {"document_id": "doc-a", "chunk_index": 0})()]
        p = tmp_path / "bad.jsonl"
        p.write_text(
            json.dumps({"query_id": "q1", "query": "a", "relevant": [{"document_id": "doc-missing", "chunk_index": 0, "grade": 1}]}) + "\n",
            encoding="utf-8",
        )
        with pytest.raises(GoldenSetError, match="not found in corpus"):
            load_golden_set(str(p), corpus)


class TestRunIdentifiesItsCorpus:
    """verification.md rows 92, 94. A score against the synthetic fixture is not
    evidence about tenant behaviour, so every report says which corpus produced it and
    a tenant run is reproducible from its configuration alone."""

    async def _report(self, corpus_name):
        from src.shared.retrieval.config import RetrievalConfig
        from src.shared.retrieval.eval.report import build_json_report
        from src.shared.retrieval.eval.runner import MatrixConfiguration, run_configuration
        from src.shared.retrieval.eval.golden_set import GoldenQuery, Judgment as GoldenJudgment
        from src.shared.retrieval.models import RetrievalResult
        from src.shared.retrieval.eval.runner import MatrixResult
        from src.shared.retrieval.tools.base import ToolContext, ToolResult

        class _Tool:
            name = "semantic_retrieval"

            async def call(self, args, context):
                return ToolResult(tool_name="semantic_retrieval", results=[
                    RetrievalResult(document_id="doc-a", chunk_index=0, chunk_text="c", similarity_score=0.9),
                ])

        class _Registry:
            def get(self, name):
                return _Tool()

        queries = [
            GoldenQuery(query_id="q0", query="q", query_class="simple_structured",
                        relevant=[GoldenJudgment(document_id="doc-a", chunk_index=0, grade=2)]),
        ]
        config = MatrixConfiguration(
            name="dense", retrieval_config=RetrievalConfig(), corpus=corpus_name,
        )
        result = await run_configuration(
            queries, config, lambda cfg, q: ToolContext(tenant_id="t", schema="s", session=object()),
            registry_factory=lambda: _Registry(), k=5,
        )
        return build_json_report("set", 1, MatrixResult(configurations=[result])), result

    @pytest.mark.asyncio
    async def test_report_names_corpus(self):
        from src.shared.retrieval.eval.metrics import SCORING_RULE
        from src.shared.retrieval.eval.runner import TENANT_CORPUS

        report, _ = await self._report(TENANT_CORPUS)

        assert report["corpus"] == TENANT_CORPUS
        assert report["scoring_rule"] == SCORING_RULE
        assert report["configurations"][0]["corpus"] == TENANT_CORPUS

    @pytest.mark.asyncio
    async def test_tenant_corpus_run_is_reproducible(self):
        from src.shared.retrieval.eval.runner import TENANT_CORPUS

        first, first_result = await self._report(TENANT_CORPUS)
        second, second_result = await self._report(TENANT_CORPUS)

        assert first_result.aggregate == second_result.aggregate
        assert first["corpus"] == second["corpus"]
        assert [q for q in first["per_query"]] == [q for q in second["per_query"]]

    def test_committed_baseline_records_its_rule_and_corpus(self):
        from src.shared.retrieval.eval.metrics import SCORING_RULE
        from src.shared.retrieval.eval.runner import SYNTHETIC_CORPUS

        with open(os.path.join(FIXTURES_DIR, "baseline.json"), encoding="utf-8") as f:
            baseline = json.load(f)

        assert baseline["scoring_rule"] == SCORING_RULE
        assert baseline["corpus"] == SYNTHETIC_CORPUS
        # Regenerated under the new rule: every query in this deterministic fixture set
        # succeeds, so the two rules agree on the numbers and the labels are what make
        # a future divergence visible.
        assert baseline["degraded_count"] == 0
        assert baseline["failed_count"] == 0


class TestEmbeddingModelMismatch:
    """Covers verification.md row 46."""

    def test_embedding_model_mismatch_fails(self):
        with pytest.raises(EmbeddingModelMismatchError):
            PrecomputedEmbeddingService(EMBEDDINGS_PATH, expected_model="text-embedding-3-small")

    def test_matching_model_loads(self):
        service = PrecomputedEmbeddingService(EMBEDDINGS_PATH, expected_model="synthetic-hash-embedding-v1")
        corpus = load_corpus(CORPUS_PATH)
        vec = service.chunk_embedding(corpus[0].document_id, corpus[0].chunk_index)
        assert len(vec) == 1536
