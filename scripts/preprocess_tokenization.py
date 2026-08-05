"""Repairs recoverable tokenization damage in annotations.jsonl before NAME
labeling: private-use-area icon glyphs (from PDF icon fonts) that ate the
whitespace around them, and fields glued together without a separator where
a comma/colon/camelCase boundary is still visible in the text.

Deliberately does NOT touch character-shattered tokens (single letters split
by the original PDF extraction) -- that's a loss of spatial layout info at
the source, not something recoverable by resplitting a flat token list.
Records flagged as shattered are left untouched and reported separately.

Each split token inherits its parent's tag: first piece keeps the original
B-/I- tag, subsequent pieces get I- of the same type (or stay O).
"""
import json
import re

# Private-use-area codepoints used by icon fonts (Font Awesome etc.) in PDF text extraction,
# plus the generic Unicode replacement character left by bad decoding.
_PUA_RE = re.compile(u"[-�]")

# Split points that are unambiguous: a comma/semicolon not followed by whitespace,
# or a label like "Phone:"/"Email:" glued onto the next field.
_DELIM_SPLIT_RE = re.compile(r"(?<=[,;])(?=\S)|(?<=[a-zA-Z0-9]):(?=[A-Za-z0-9])")

# camelCase boundary: lowercase/digit followed by uppercase.
_CAMEL_SPLIT_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")

# A run of 6+ digits (phone number) immediately followed by letters with no
# separator -- e.g. "7907101056asuhail415@gmail.com" (phone glued to email).
_DIGITRUN_SPLIT_RE = re.compile(r"(?<=\d{6})(?=[A-Za-z])")


def is_shattered(tokens):
    if not tokens:
        return False
    single_char = sum(1 for t in tokens if len(t) == 1 and t.isalpha())
    return single_char / len(tokens) > 0.15


def split_token(token):
    cleaned = _PUA_RE.sub("", token)
    if not cleaned:
        return []
    pieces = [cleaned]
    pieces = [p for chunk in pieces for p in _DELIM_SPLIT_RE.split(chunk) if p]
    pieces = [p for chunk in pieces for p in _CAMEL_SPLIT_RE.split(chunk) if p]
    pieces = [p for chunk in pieces for p in _DIGITRUN_SPLIT_RE.split(chunk) if p]
    return pieces if pieces else [cleaned]


def repair_record(tokens, tags):
    new_tokens, new_tags = [], []
    for tok, tag in zip(tokens, tags):
        pieces = split_token(tok)
        if len(pieces) <= 1:
            new_tokens.append(pieces[0] if pieces else tok)
            new_tags.append(tag)
            continue
        base = tag[2:] if tag.startswith(("B-", "I-")) else None
        for i, piece in enumerate(pieces):
            new_tokens.append(piece)
            if base is None:
                new_tags.append("O")
            else:
                new_tags.append("B-" + base if i == 0 and tag.startswith("B-") else "I-" + base)
    return new_tokens, new_tags


def main():
    with open("annotations.jsonl", encoding="utf-8") as f:
        recs = [json.loads(l) for l in f]

    out_recs = []
    shattered_idxs = []
    split_count = 0
    for idx, r in enumerate(recs):
        tokens, tags = r["tokens"], r["tags"]
        if is_shattered(tokens):
            shattered_idxs.append(idx)
            out_recs.append({"tokens": tokens, "tags": tags})
            continue
        new_tokens, new_tags = repair_record(tokens, tags)
        if len(new_tokens) != len(tokens):
            split_count += 1
        out_recs.append({"tokens": new_tokens, "tags": new_tags})

    with open("annotations.jsonl.preprocessed", "w", encoding="utf-8") as out:
        for r in out_recs:
            out.write(json.dumps(r, ensure_ascii=False) + "\n")

    print("records: " + str(len(recs)))
    print("records with tokens re-split: " + str(split_count))
    print("shattered records left untouched: " + str(len(shattered_idxs)) + " -> " + str(shattered_idxs))
    print("wrote annotations.jsonl.preprocessed")


if __name__ == "__main__":
    main()
