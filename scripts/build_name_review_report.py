"""Builds a human-readable review report comparing annotations.jsonl (source)
against annotations.jsonl.labeled (output of label_person_names.py --apply).
For each record, shows the extracted NAME span (if any) with surrounding
token context, so a reviewer can quickly accept/reject/fix each one without
reading raw token/tag arrays.
"""
import json


def load(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def name_span(tags):
    start = None
    for i, t in enumerate(tags):
        if t == "B-NAME":
            start = i
        elif t == "I-NAME" and start is None:
            start = i
        elif t not in ("B-NAME", "I-NAME") and start is not None:
            return start, i
    if start is not None:
        return start, len(tags)
    return None


def main():
    src = load("annotations.jsonl")
    labeled = load("annotations.jsonl.labeled")
    assert len(src) == len(labeled), f"record count mismatch: {len(src)} vs {len(labeled)}"

    found, missing = [], []
    for i, (s, l) in enumerate(zip(src, labeled)):
        tokens = l["tokens"]
        span = name_span(l["tags"])
        if span:
            start, end = span
            ctx_before = " ".join(tokens[max(0, start - 5):start])
            name = " ".join(tokens[start:end])
            ctx_after = " ".join(tokens[end:end + 5])
            found.append((i, name, ctx_before, ctx_after))
        else:
            missing.append((i, " ".join(tokens[:12])))

    with open("scripts/name_review_report.txt", "w", encoding="utf-8") as out:
        out.write(f"NAME labeling review — {len(found)}/{len(src)} records labeled, {len(missing)} unlabeled\n")
        out.write("=" * 80 + "\n\n")
        out.write("--- LABELED (verify these) ---\n\n")
        for i, name, before, after in found:
            out.write(f"[{i:>3}] NAME = {name!r}\n")
            out.write(f"      context: ...{before} [[{name}]] {after}...\n\n")
        out.write("\n--- UNLABELED (needs manual attention) ---\n\n")
        for i, preview in missing:
            out.write(f"[{i:>3}] {preview}\n")

    print(f"labeled={len(found)} unlabeled={len(missing)} -> scripts/name_review_report.txt")


if __name__ == "__main__":
    main()
