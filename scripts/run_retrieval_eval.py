"""CLI entry point for the retrieval eval harness.

Seeds the committed synthetic corpus into a disposable schema, runs the golden set
through the tool layer under a configuration matrix, and writes a JSON + Markdown
report. By default uses the committed precomputed embeddings (no network calls);
pass --live-embeddings to embed the golden set live instead (requires
NER_OPENAI_API_KEY / Azure OpenAI configuration).

Usage:
    python scripts/run_retrieval_eval.py [--k 5] [--output-dir DIR] [--write-baseline]
"""
import argparse
import asyncio
import os
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.shared.config import settings
from src.shared.retrieval.config import RetrievalConfig
from src.shared.retrieval.eval.embeddings import PrecomputedEmbeddingService, QueryIdEmbeddingService
from src.shared.retrieval.eval.golden_set import load_corpus, load_golden_set
from src.shared.retrieval.eval.report import build_json_report, write_report
from src.shared.retrieval.eval.runner import MatrixConfiguration, MatrixResult, run_configuration
from src.shared.retrieval.retriever import DenseRetriever, HybridRetriever, SparseRetriever
from src.shared.retrieval.tools.base import ToolContext

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures", "retrieval_eval")
EVAL_SCHEMA = "tenant_retrieval_eval"


async def _create_schema(engine, corpus, chunk_embeddings) -> None:
    async with engine.begin() as conn:
        await conn.execute(text(f"DROP SCHEMA IF EXISTS {EVAL_SCHEMA} CASCADE"))
        await conn.execute(text(f"CREATE SCHEMA {EVAL_SCHEMA}"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text(f"""
            CREATE TABLE {EVAL_SCHEMA}.documents (
                id VARCHAR PRIMARY KEY, tenant_id VARCHAR NOT NULL, filename VARCHAR(255) NOT NULL,
                status VARCHAR(20) DEFAULT 'processed', purpose VARCHAR(20) NOT NULL DEFAULT 'query'
            )
        """))
        await conn.execute(text(f"""
            CREATE TABLE {EVAL_SCHEMA}.document_chunks (
                id VARCHAR PRIMARY KEY, document_id VARCHAR NOT NULL, chunk_index INTEGER NOT NULL,
                chunk_text TEXT NOT NULL, embedding vector(1536),
                page_number INTEGER, char_start INTEGER, char_end INTEGER,
                purpose VARCHAR(20) NOT NULL DEFAULT 'query',
                chunk_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', chunk_text)) STORED
            )
        """))
        doc_ids = sorted({c.document_id for c in corpus})
        for doc_id in doc_ids:
            await conn.execute(
                text(f"INSERT INTO {EVAL_SCHEMA}.documents (id, tenant_id, filename, status, purpose) VALUES (:id, 'eval-tenant', :fn, 'processed', 'query')"),
                {"id": doc_id, "fn": f"{doc_id}.txt"},
            )
        for chunk in corpus:
            vec = chunk_embeddings[f"{chunk.document_id}::{chunk.chunk_index}"]
            emb_str = "[" + ",".join(str(v) for v in vec) + "]"
            await conn.execute(
                text(f"""
                    INSERT INTO {EVAL_SCHEMA}.document_chunks (id, document_id, chunk_index, chunk_text, embedding, purpose)
                    VALUES (:id, :doc_id, :idx, :txt, '{emb_str}'::vector, 'query')
                """),
                {"id": str(uuid.uuid4()), "doc_id": chunk.document_id, "idx": chunk.chunk_index, "txt": chunk.chunk_text},
            )


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--output-dir", default=FIXTURES_DIR)
    parser.add_argument("--write-baseline", action="store_true")
    args = parser.parse_args()

    corpus = load_corpus(os.path.join(FIXTURES_DIR, "corpus.jsonl"))
    golden_queries = load_golden_set(os.path.join(FIXTURES_DIR, "golden_set.jsonl"), corpus)

    embeddings_path = os.path.join(FIXTURES_DIR, "embeddings.json")
    provider = PrecomputedEmbeddingService(embeddings_path, expected_model="synthetic-hash-embedding-v1")
    query_text_to_id = {q.query: q.query_id for q in golden_queries}
    embedding_service = QueryIdEmbeddingService(provider, query_text_to_id)

    import json
    with open(embeddings_path, encoding="utf-8") as f:
        chunk_embeddings = json.load(f)["chunks"]

    engine = create_async_engine(settings.database_url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    try:
        await _create_schema(engine, corpus, chunk_embeddings)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        configurations = [
            MatrixConfiguration("dense_only", RetrievalConfig(top_k=args.k)),
            MatrixConfiguration("hybrid", RetrievalConfig(top_k=args.k)),
        ]

        # One session per configuration, reused sequentially across its queries —
        # avoids leaking a connection per query (HybridRetriever also relies on
        # sequential, not concurrent, use of a single AsyncSession; see retriever.py).
        config_results = []
        for config in configurations:
            async with session_factory() as session:
                dense = DenseRetriever(embedding_service, config=config.retrieval_config)
                if config.name == "dense_only":
                    retriever = dense
                else:
                    retriever = HybridRetriever(dense, SparseRetriever(config=config.retrieval_config), config=config.retrieval_config)
                context = ToolContext(tenant_id="eval-tenant", schema=EVAL_SCHEMA, session=session, retriever=retriever, max_top_k=50)

                def context_factory(cfg, query, _context=context):
                    return _context

                config_results.append(await run_configuration(golden_queries, config, context_factory, k=args.k))

        matrix = MatrixResult(configurations=config_results)
        report = build_json_report("retrieval_eval/golden_set.jsonl", len(golden_queries), matrix)

        os.makedirs(args.output_dir, exist_ok=True)
        write_report(report, os.path.join(args.output_dir, "report.json"), os.path.join(args.output_dir, "report.md"))
        print(f"Wrote report to {args.output_dir}/report.json and report.md")

        if args.write_baseline:
            best = max((c for c in matrix.configurations if c.aggregate and c.degraded_query_count == 0), key=lambda c: c.aggregate.ndcg_at_k)
            baseline = {
                "configuration": best.name,
                "recall_at_k": best.aggregate.recall_at_k,
                "precision_at_k": best.aggregate.precision_at_k,
                "mrr_at_k": best.aggregate.mrr_at_k,
                "ndcg_at_k": best.aggregate.ndcg_at_k,
                "query_count": best.aggregate.query_count,
                "k": args.k,
            }
            with open(os.path.join(args.output_dir, "baseline.json"), "w", encoding="utf-8") as f:
                json.dump(baseline, f, indent=2, sort_keys=True)
            print(f"Wrote baseline from configuration '{best.name}': {baseline}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
