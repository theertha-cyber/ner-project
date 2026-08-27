# Entity-quality evaluation fixture

Every case in `fixture.jsonl` is taken from a real document in the development tenant
`d2eb33ab-68f1-4e67-a841-f040f7eaf233`. `tokens` is the document text tokenized the way
`worker._tokenize_span` does (whitespace, `\S+`), and `predictions` is the BIO sequence
the fine-tuned model actually produced for those words, recorded from
`extracted_entities`. Replaying a case therefore exercises the same input the production
pipeline saw, not a synthetic approximation.

`expected` is the human-labelled correct answer. The loader refuses any case whose
expected value is not a substring of the source text — a fixture whose "correct" answer
is absent from the document would make every configuration look like it hallucinated, or
excuse one that did.

`confidence` values are calibrated probabilities. The rows these cases were drawn from
carry raw logits (2.85–7.44 on the live tenant), which are not comparable across
documents; the fixture states the probability the calibrated pipeline produces, since
that is the scale candidate selection is expressed in.

## Failure classes

Every class in `fixture.REQUIRED_CLASSES` must have at least one case, or `load_fixture`
raises. A fixture that quietly loses coverage of a class stops being evidence about that
class while still reporting a number.

| Class | Origin on the live tenant |
|---|---|
| `correct_extraction` | Rows that must survive every configuration unchanged |
| `entity_type_error` | `B-COMPANY HANNAH`, `B-DEGREE JAVA`, `B-ADDRESS Arjun` |
| `fragmented_span` | `two` / `half years` from `resume - MAHALAKSHMI S.pdf` |
| `malformed_value` | `PHONE_NUMBER Z5060835` (a passport number), `COMPANY ,` |
| `format_characters` | The nine rows carrying U+200B, four carrying U+2019 |
| `duplicate_mentions` | `node.js` ×8 and `react` ×6 in one document |
| `duration_numeric` | `2 years of experience,` from `Resume RENJIEAPEN.pdf` |
| `date_value` | Typed date parsing |
| `organization_name` | `Centizen Inc.`, `Manappuram Finance Ltd.` |
| `person_name` | `ZANITH KUMAR R`, `GIRISH K.G` |
| `multi_token` | `College of Engineering Kallooppara` |

## Regenerating

The cases are hand-labelled and checked in deliberately: they are the ground truth the
three-configuration comparison is scored against, so they must not move when the
pipeline does. Add a case by appending a line; the loader validates it on the next run.
