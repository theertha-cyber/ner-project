"""Deterministic cleanup pass over annotations.jsonl.labeled's NAME spans.
Trims spans that bled into job titles, tech terms, section headers, address
text, or generic English words. Un-names (reverts to O) spans with no
recoverable name tokens at all. Prints a diff so every change is visible.
"""
import json
import re

BLOCKLIST = {
    # section headers / objective boilerplate
    "career", "objective", "summary", "profile", "resume", "curriculum", "vitae",
    "to", "work", "in", "a", "the", "and", "of", "on", "with", "for", "that", "where",
    "i", "can", "my", "an", "is", "as", "at", "by", "from", "or", "this",
    "dynamically", "growing", "organization", "facilitate", "growth", "talent",
    "excel", "professional", "career.", "contribute", "success", "team", "role",
    # job titles / tech terms
    "developer", "engineer", "software", "full", "stack", "web", "android", "ios",
    "angular", "react", "python", "java", "javascript", "node", "manager", "analyst",
    "consultant", "intern", "senior", "junior", "lead", "architect", "experience",
    "contact", "last", "updated", "sree", "dhanya",
    # address / house-name markers (common Malayalam/Indian address conventions)
    "house", "nagar", "road", "street", "po", "kerala", "veedu", "parampil",
    "puthenvilaveedu", "edakkandam", "keerthi", "vellayani", "muthanikkatt",
}

_INVOCATION_RE = re.compile(r"^(om|ga|nesha)$", re.IGNORECASE)


def _clean_word(tok: str) -> str:
    return re.sub(r"[^A-Za-z]", "", tok).lower()


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


def clean_span(tokens, start, end):
    """Returns (new_start, new_end) or None if nothing salvageable.
    Strategy: walk tokens in the span, drop leading invocation words, stop at
    the first blocklisted/stopword/junk token, keep everything before it."""
    idx = start
    # skip leading invocation tokens (e.g. "Om Ga nesha" before the real name)
    while idx < end and _INVOCATION_RE.match(tokens[idx]):
        idx += 1
    if idx >= end:
        return None
    new_start = idx
    new_end = idx
    for i in range(idx, end):
        word = _clean_word(tokens[i])
        if not word:
            # punctuation-only token (".", ",") inside a name is fine, keep scanning
            new_end = i + 1
            continue
        if word in BLOCKLIST or "@" in tokens[i] or re.search(r"\d{3,}", tokens[i]):
            break
        new_end = i + 1
    if new_end <= new_start:
        return None
    return new_start, new_end


def main():
    with open("annotations.jsonl.labeled", encoding="utf-8") as f:
        recs = [json.loads(l) for l in f]

    changed, reverted, kept = 0, 0, 0
    for idx, r in enumerate(recs):
        tags = r["tags"]
        span = name_span(tags)
        if not span:
            continue
        start, end = span
        original_text = " ".join(r["tokens"][start:end])
        cleaned = clean_span(r["tokens"], start, end)

        # wipe the whole original span first
        for i in range(start, end):
            tags[i] = "O"

        if cleaned is None:
            reverted += 1
            print(f"[{idx:>3}] REVERTED (no salvageable name): {original_text!r}")
            continue

        new_start, new_end = cleaned
        for i in range(new_start, new_end):
            tags[i] = "B-NAME" if i == new_start else "I-NAME"
        new_text = " ".join(r["tokens"][new_start:new_end])
        if (new_start, new_end) != (start, end):
            changed += 1
            print(f"[{idx:>3}] TRIMMED: {original_text!r}  ->  {new_text!r}")
        else:
            kept += 1

    with open("annotations.jsonl.cleaned", "w", encoding="utf-8") as out:
        for r in recs:
            out.write(json.dumps({"tokens": r["tokens"], "tags": r["tags"]}, ensure_ascii=False) + "\n")

    print(f"\nkept={kept} trimmed={changed} reverted={reverted} -> annotations.jsonl.cleaned")


if __name__ == "__main__":
    main()
