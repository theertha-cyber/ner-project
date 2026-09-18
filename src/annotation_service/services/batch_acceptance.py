"""Sampling and agreement measurement for the batch acceptance gate.

Pure functions: document ids and reviewer dispositions in, a sample and a rate out. The database
work and the promotion live in the API layer, so the two things worth arguing about — which
documents get reviewed, and what "agreed" means — can be read and tested on their own.

Nothing here decides whether a batch is accepted. The threshold comparison is one line in the
caller; keeping it there rather than here is what makes it obvious that there is exactly one
such comparison and no partial-acceptance path beside it (design.md Decision 3).
"""

import random

# What a reviewer can say about one suggested span.
#
# Only `agree` counts toward the rate — an exact match, same entity type and same offsets, which
# is the definition of agreement this change adopted (design.md, task 1.4). The other three are
# all disagreement for gating purposes, and they are separate values anyway because a boundary
# nudged by one token and a hallucinated entity deleted outright are different facts about the
# model. The gate cannot currently tell them apart; the stored dispositions can, and that is
# what a later, evidence-based threshold will be derived from.
DISPOSITION_AGREE = "agree"
DISPOSITION_BOUNDARY = "boundary"
DISPOSITION_RETYPE = "retype"
DISPOSITION_REJECT = "reject"

DISPOSITIONS = (
    DISPOSITION_AGREE,
    DISPOSITION_BOUNDARY,
    DISPOSITION_RETYPE,
    DISPOSITION_REJECT,
)


def draw_sample(
    document_ids: list[str],
    sample_size: int,
    sampling_enabled: bool,
    rng: random.Random | None = None,
) -> list[str]:
    """The documents a reviewer will check.

    With sampling disabled the sample is the whole batch, which is how "require full review"
    is expressed — one code path, not a second mode. With it enabled the sample is drawn
    uniformly at random across the entire batch: not the first N, which are frequently the most
    similar documents in an upload and would produce a rate that does not generalise, and not
    the reviewer's own choice, which is selection bias by construction (design.md Decision 4).

    `rng` is injectable so a test can pin the draw; it is never seeded in production, where an
    unpredictable sample is the point.
    """
    if not sampling_enabled or sample_size >= len(document_ids):
        return list(document_ids)
    chooser = rng or random.SystemRandom()
    return chooser.sample(list(document_ids), sample_size)


def agreement_rate(dispositions: list[dict]) -> tuple[int, int, float | None]:
    """`(agreed, reviewed, rate)` from the reviewer's per-suggestion dispositions.

    The rate is `None` when nothing was reviewed. That is deliberately not `1.0`: a sample
    containing no suggestions at all has measured nothing, and returning a perfect score for it
    would let an empty measurement clear any threshold.
    """
    reviewed = len(dispositions)
    if reviewed == 0:
        return 0, 0, None
    agreed = sum(
        1 for disposition in dispositions if disposition.get("disposition") == DISPOSITION_AGREE
    )
    return agreed, reviewed, agreed / reviewed
