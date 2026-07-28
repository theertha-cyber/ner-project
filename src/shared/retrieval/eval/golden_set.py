import json
from dataclasses import dataclass, field
from pathlib import Path


class GoldenSetError(Exception):
    pass


@dataclass(frozen=True)
class Judgment:
    document_id: str
    chunk_index: int
    grade: int


@dataclass(frozen=True)
class GoldenQuery:
    query_id: str
    query: str
    relevant: list[Judgment] = field(default_factory=list)
    notes: str | None = None


@dataclass(frozen=True)
class CorpusChunk:
    document_id: str
    chunk_index: int
    chunk_text: str


def load_corpus(path: str | Path) -> list[CorpusChunk]:
    chunks: list[CorpusChunk] = []
    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                raise GoldenSetError(f"corpus.jsonl line {line_no}: invalid JSON: {e}") from e
            document_id = record.get("document_id")
            if not document_id:
                raise GoldenSetError(f"corpus.jsonl line {line_no}: missing document_id")
            for chunk in record.get("chunks", []):
                chunks.append(CorpusChunk(
                    document_id=document_id,
                    chunk_index=chunk["chunk_index"],
                    chunk_text=chunk["chunk_text"],
                ))
    return chunks


def load_golden_set(path: str | Path, corpus: list[CorpusChunk] | None = None) -> list[GoldenQuery]:
    corpus_keys = {(c.document_id, c.chunk_index) for c in corpus} if corpus is not None else None

    queries: list[GoldenQuery] = []
    seen_ids: set[str] = set()

    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                raise GoldenSetError(f"golden_set.jsonl line {line_no}: invalid JSON: {e}") from e

            query_id = record.get("query_id")
            query_text = record.get("query")
            relevant_raw = record.get("relevant")

            if not query_id or not isinstance(query_id, str):
                raise GoldenSetError(f"golden_set.jsonl line {line_no}: missing or invalid query_id")
            if not query_text or not isinstance(query_text, str):
                raise GoldenSetError(f"golden_set.jsonl line {line_no}: missing or invalid query")
            if relevant_raw is None or not isinstance(relevant_raw, list):
                raise GoldenSetError(f"golden_set.jsonl line {line_no}: 'relevant' must be a list")

            if query_id in seen_ids:
                raise GoldenSetError(f"duplicate query_id: '{query_id}'")
            seen_ids.add(query_id)

            judgments: list[Judgment] = []
            for j in relevant_raw:
                document_id = j.get("document_id")
                chunk_index = j.get("chunk_index")
                grade = j.get("grade")
                if not document_id or not isinstance(chunk_index, int) or not isinstance(grade, int):
                    raise GoldenSetError(f"query '{query_id}': malformed relevant entry: {j}")
                if not (0 <= grade <= 3):
                    raise GoldenSetError(f"query '{query_id}': grade {grade} out of range 0..3")
                if corpus_keys is not None and (document_id, chunk_index) not in corpus_keys:
                    raise GoldenSetError(
                        f"query '{query_id}': relevant entry ({document_id}, {chunk_index}) not found in corpus"
                    )
                judgments.append(Judgment(document_id=document_id, chunk_index=chunk_index, grade=grade))

            queries.append(GoldenQuery(query_id=query_id, query=query_text, relevant=judgments, notes=record.get("notes")))

    return queries
