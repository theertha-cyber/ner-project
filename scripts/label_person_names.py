"""One-off script: identifies the resume owner's own name span in each
annotations.jsonl record via an LLM call and adds B-NAME/I-NAME tags.
Never overwrites an existing non-"O" tag. Run with --sample N to only
process a random sample and write results to a review file without
touching the source; run with --apply to write the full labeled file.
"""
import argparse
import asyncio
import json
import random
import sys

from openai import AsyncAzureOpenAI

from src.shared.config import settings

SYSTEM_PROMPT = """You identify the resume owner's own name in a list of tokens extracted \
from a resume/CV document (tokenization may be noisy: OCR artifacts, headers like "RESUME" \
or "CURRICULUM VITAE", invocation lines, single characters from split words).

You are given an enumerated list of tokens (index: token) and their current NER tag \
("O" means untagged and eligible; anything else is already labeled and off-limits).

Return ONLY the token index range of the CANDIDATE'S OWN FULL NAME (not a company, not a \
reference's name, not a section header) as JSON: {"start": <int>, "end": <int>} where the \
range is inclusive of start and exclusive of end (Python slice semantics), and every token \
in that range currently has tag "O". If you cannot confidently identify the candidate's own \
name in the given tokens, return {"start": null, "end": null}.

The name is typically 2-4 tokens (or more if the source text is letter-split, e.g. "S O O R A J"). \
STOP the range before any of the following even if they immediately follow the name with no \
separator: a house/building name (Indian resumes often prefix or follow the name with a house \
name, e.g. "Muthanikkatt House", "Puthenvilaveedu"), a street/place name, "PO"/pin code, a job \
title or "Software/Web/Full Stack Developer"-style phrase, a section header ("OBJECTIVE", \
"SUMMARY", "CAREER", "EXPERIENCE", "CONTACT"), or ordinary sentence text. If the candidate's own \
name is not clearly separable from surrounding text within these rules, prefer returning \
{"start": null, "end": null} over guessing a wider span. No explanation, JSON only."""


def build_client() -> AsyncAzureOpenAI:
    return AsyncAzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.openai_api_key,
        api_version=settings.azure_openai_api_version,
    )


async def find_name_span(client: AsyncAzureOpenAI, tokens: list[str], tags: list[str], window: int = 60) -> tuple[int, int] | None:
    n = min(window, len(tokens))
    enumerated = "\n".join(f"{i}: {tokens[i]!r} (tag={tags[i]})" for i in range(n))
    resp = await client.chat.completions.create(
        model=settings.azure_openai_chat_deployment,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": enumerated},
        ],
        temperature=0,
        max_tokens=50,
        response_format={"type": "json_object"},
    )
    try:
        data = json.loads(resp.choices[0].message.content)
    except (json.JSONDecodeError, TypeError):
        return None
    start, end = data.get("start"), data.get("end")
    if start is None or end is None:
        return None
    if not (0 <= start < end <= n):
        return None
    if any(tags[i] != "O" for i in range(start, end)):
        return None
    return start, end


async def process_record(client: AsyncAzureOpenAI, record: dict) -> dict:
    tokens, tags = record["tokens"], list(record["tags"])
    span = await find_name_span(client, tokens, tags)
    result = {"tokens": tokens, "tags_before": list(tags), "name_span": None, "name_text": None}
    if span:
        start, end = span
        for i in range(start, end):
            tags[i] = "B-NAME" if i == start else "I-NAME"
        result["name_span"] = [start, end]
        result["name_text"] = " ".join(tokens[start:end])
    result["tags_after"] = tags
    return result


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=0, help="Process only a random sample of N records, write review file, don't touch source")
    parser.add_argument("--apply", action="store_true", help="Process all records and write the labeled output file")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--src", type=str, default="annotations.jsonl")
    args = parser.parse_args()

    src_path = args.src
    with open(src_path, encoding="utf-8") as f:
        lines = [json.loads(l) for l in f if l.strip()]

    client = build_client()

    if args.sample:
        random.seed(args.seed)
        idxs = sorted(random.sample(range(len(lines)), min(args.sample, len(lines))))
        results = []
        for idx in idxs:
            r = await process_record(client, lines[idx])
            r["record_index"] = idx
            results.append(r)
            found = "FOUND" if r["name_span"] else "NONE"
            print(f"[{idx}] {found}: {r['name_text']!r}")
        with open("scripts/_name_labeling_sample_review.jsonl", "w", encoding="utf-8") as out:
            for r in results:
                out.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"\nWrote {len(results)} sample results to scripts/_name_labeling_sample_review.jsonl")
        return

    if args.apply:
        out_lines = []
        found_count = 0
        skipped_shattered = 0
        for i, rec in enumerate(lines):
            toks = rec["tokens"]
            single_char = sum(1 for t in toks if len(t) == 1 and t.isalpha())
            if toks and single_char / len(toks) > 0.15:
                out_lines.append({"tokens": toks, "tags": rec["tags"]})
                skipped_shattered += 1
                continue
            r = await process_record(client, rec)
            if r["name_span"]:
                found_count += 1
            out_lines.append({"tokens": r["tokens"], "tags": r["tags_after"]})
            if i % 25 == 0:
                print(f"...{i}/{len(lines)}", file=sys.stderr)
        with open("annotations.jsonl.labeled", "w", encoding="utf-8") as out:
            for rec in out_lines:
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"Labeled {found_count}/{len(lines)} records, skipped {skipped_shattered} shattered. Wrote annotations.jsonl.labeled (review before replacing source).")
        return

    parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
