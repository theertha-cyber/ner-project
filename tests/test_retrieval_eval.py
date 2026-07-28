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
