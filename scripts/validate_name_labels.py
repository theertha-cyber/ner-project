"""Deterministic post-validation safety net over annotations.jsonl.labeled's
NAME spans. Unlike the earlier blocklist attempt, this only inspects tokens
of length >= 2 for blocklist membership -- single-character tokens (common
in letter-split OCR names) are never compared against the stopword/blocklist
set, avoiding the "A"/"I" initial-vs-stopword collision that corrupted the
first cleanup pass.

Truncates (never blindly reverts) a span at the first token that:
  - contains a digit or "/" (names don't; house numbers, pins, phone numbers do), or
  - is a blocklisted word (job title / section header / address marker),
    only when the token is 2+ characters.
Drops the span entirely if nothing salvageable remains before the cut point.
"""
import json
import re

BLOCKLIST = {
    "career", "objective", "summary", "profile", "resume", "curriculum", "vitae",
    "developer", "engineer", "software", "full", "stack", "web", "android", "ios",
    "angular", "react", "python", "java", "javascript", "node", "manager", "analyst",
    "consultant", "intern", "senior", "junior", "lead", "architect", "experience",
    "contact", "house", "nagar", "road", "street", "kerala", "veedu", "email",
    "mobile", "phone", "mob", "pin", "po", "professional", "personal",
}

MAX_WORD_SPAN = 5  # real (non letter-split) names: cap token count


def _clean(tok: str) -> str:
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


def _contains_blocklisted_substring(joined: str) -> int | None:
    """Returns the char offset where a blocklisted word starts inside the
    concatenated (letters-only, lowercase) span text, or None. Catches a
    blocklisted word spread across single-character tokens (e.g. "A N DR
    O I D" reconstructing to "android"), which per-token checks miss."""
    for word in BLOCKLIST:
        if len(word) < 4:
            continue  # short words risk false positives inside real names
        idx = joined.find(word)
        if idx != -1:
            return idx
    return None


def validate(tokens, start, end):
    is_letter_split = all(len(t) <= 2 for t in tokens[start:end])
    new_end = start
    for i in range(start, end):
        tok = tokens[i]
        if re.search(r"\d", tok) or "/" in tok:
            break
        word = _clean(tok)
        if len(word) >= 2 and word in BLOCKLIST:
            break
        new_end = i + 1
        if tok.endswith(","):
            break  # comma marks an address-list continuation, stop here

    if new_end <= start:
        return None

    # substring scan across the whole reconstructed span, char offset -> token index
    offsets, joined = [], ""
    for i in range(start, new_end):
        joined += _clean(tokens[i])
        offsets.append((len(joined), i))
    hit = _contains_blocklisted_substring(joined)
    if hit is not None:
        for char_len, tok_idx in offsets:
            if char_len > hit:
                new_end = tok_idx
                break
        else:
            new_end = start

    if new_end <= start:
        return None
    if not is_letter_split and (new_end - start) > MAX_WORD_SPAN:
        new_end = start + MAX_WORD_SPAN
    return start, new_end


def main():
    with open("annotations.jsonl.labeled", encoding="utf-8") as f:
        recs = [json.loads(l) for l in f]

    kept, truncated, dropped = 0, 0, 0
    for r in recs:
        tags = r["tags"]
        span = name_span(tags)
        if not span:
            continue
        start, end = span
        result = validate(r["tokens"], start, end)
        for i in range(start, end):
            tags[i] = "O"
        if result is None:
            dropped += 1
            continue
        new_start, new_end = result
        for i in range(new_start, new_end):
            tags[i] = "B-NAME" if i == new_start else "I-NAME"
        if (new_start, new_end) == (start, end):
            kept += 1
        else:
            truncated += 1

    with open("annotations.jsonl.validated", "w", encoding="utf-8") as out:
        for r in recs:
            out.write(json.dumps({"tokens": r["tokens"], "tags": r["tags"]}, ensure_ascii=False) + "\n")

    print(f"kept={kept} truncated={truncated} dropped={dropped} -> annotations.jsonl.validated")


if __name__ == "__main__":
    main()
