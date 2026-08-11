"""Guards against the silent-truncation bug: `_infer_with_onnx()` used to tokenize the
whole document with `truncation=True` against a 512-position BERT, so every document
longer than ~277 whitespace words lost its tail with no error, no warning and no log.
Roughly half of every long document was never shown to the model."""

import os

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")

import numpy as np
import pytest

from src.model_serving.services import inference_service
from src.model_serving.services.inference_service import (
    MODEL_MAX_POSITIONS,
    NUM_SPECIAL_TOKENS,
    _build_windows,
    _window_geometry,
)
from src.shared.config import settings


class TestWindowGeometry:
    def test_window_plus_special_tokens_stays_under_model_limit(self, monkeypatch):
        monkeypatch.setattr(settings, "inference_window_size", 400)
        monkeypatch.setattr(settings, "inference_window_overlap", 50)
        budget, overlap = _window_geometry()
        assert budget + NUM_SPECIAL_TOKENS <= MODEL_MAX_POSITIONS
        assert (budget, overlap) == (400, 50)

    def test_oversized_configured_window_is_clamped_to_model_limit(self, monkeypatch):
        monkeypatch.setattr(settings, "inference_window_size", 4096)
        monkeypatch.setattr(settings, "inference_window_overlap", 50)
        budget, _ = _window_geometry()
        assert budget + NUM_SPECIAL_TOKENS <= MODEL_MAX_POSITIONS

    def test_overlap_cannot_consume_the_whole_window(self, monkeypatch):
        monkeypatch.setattr(settings, "inference_window_size", 10)
        monkeypatch.setattr(settings, "inference_window_overlap", 99)
        budget, overlap = _window_geometry()
        assert overlap < budget


class TestBuildWindows:
    def test_short_input_is_a_single_window(self):
        assert _build_windows([1] * 50, budget=400, overlap=50) == [(0, 50)]

    def test_every_word_is_covered_by_some_window(self):
        piece_counts = [2] * 700  # 1400 wordpieces, far past the 512 limit
        windows = _build_windows(piece_counts, budget=400, overlap=50)
        covered = set()
        for start, end in windows:
            covered.update(range(start, end))
        assert covered == set(range(700)), "windowing must not drop any word"

    def test_no_window_exceeds_the_budget(self):
        piece_counts = [3, 1, 7, 2, 1] * 200
        budget = 400
        for start, end in _build_windows(piece_counts, budget, overlap=50):
            total = sum(piece_counts[start:end])
            assert total <= budget or (end - start) == 1

    def test_windows_overlap_by_roughly_the_requested_wordpieces(self):
        piece_counts = [1] * 1000
        windows = _build_windows(piece_counts, budget=400, overlap=50)
        assert len(windows) > 1
        first_end = windows[0][1]
        second_start = windows[1][0]
        assert first_end - second_start == 50

    def test_windows_always_advance_even_when_one_word_fills_the_budget(self):
        """A single monster token must not wedge the walk into an infinite loop."""
        piece_counts = [1, 900, 1, 1]
        windows = _build_windows(piece_counts, budget=400, overlap=50)
        starts = [w[0] for w in windows]
        assert starts == sorted(set(starts)), "window starts must strictly increase"
        covered = set()
        for start, end in windows:
            covered.update(range(start, end))
        assert covered == {0, 1, 2, 3}

    def test_empty_input_yields_no_windows(self):
        assert _build_windows([], budget=400, overlap=50) == []


class _FakeInput:
    def __init__(self, name):
        self.name = name


def _real_piece_counts(tokens):
    """Actual WordPiece length per word, from the same tokenizer the service uses.
    Tests must not assume one piece per word — "w0" is two pieces ("w", "##0")."""
    tokenizer = inference_service._get_tokenizer()
    return inference_service._wordpiece_counts(tokenizer, tokens)


def _positions_of_word(tokens, word_index):
    """Sequence positions (including specials) that belong to `tokens[word_index]`."""
    tokenizer = inference_service._get_tokenizer()
    encoding = tokenizer(tokens, is_split_into_words=True, truncation=False)
    return {p for p, wid in enumerate(encoding.word_ids(0)) if wid == word_index}


def _fake_session(label_fn, label_count):
    """Session whose per-position argmax is driven by `label_fn(position_in_window)`."""

    class FakeSession:
        def get_inputs(self):
            return [_FakeInput("input_ids"), _FakeInput("attention_mask")]

        def run(self, output_names, inputs):
            seq_len = inputs["input_ids"].shape[1]
            logits = np.zeros((1, seq_len, label_count), dtype=np.float32)
            for pos in range(seq_len):
                chosen, score = label_fn(pos)
                logits[0, pos, chosen] = score
            return [logits]

    return FakeSession()


@pytest.fixture
def label_list():
    return ["O", "B-PROGRAMMING_LANGUAGE", "I-PROGRAMMING_LANGUAGE"]


@pytest.fixture
def patched_serving(monkeypatch, label_list):
    monkeypatch.setattr(
        inference_service, "_resolve_label_list", lambda tid: label_list
    )
    monkeypatch.setattr(
        inference_service, "_resolve_active_version", lambda tid: ("tenants/t/models/v5/", 5)
    )
    monkeypatch.setattr(settings, "inference_window_size", 400)
    monkeypatch.setattr(settings, "inference_window_overlap", 50)


class TestLongDocumentReachesTheModel:
    """The reported failure: 'Python', 'Java', 'C', 'Bash' sat at word indices 528-531
    of a 618-word resume and were truncated away before the model ever saw them."""

    def test_tail_of_a_618_word_document_is_predicted(self, monkeypatch, patched_serving, label_list):
        tokens = ["word"] * 528 + ["Python,", "Java,", "C,", "Bash"] + ["word"] * 86
        assert len(tokens) == 618

        # Label every position B-PROGRAMMING_LANGUAGE so the assertion is purely about
        # which words reached the model, not about what it decided.
        session = _fake_session(lambda pos: (1, 5.0), len(label_list))
        monkeypatch.setattr(
            inference_service.model_cache,
            "get",
            lambda mid: type("C", (), {"model": {"session": session}})(),
        )

        results = inference_service._infer_with_onnx(tokens, "t1")

        by_index = {r["word_index"]: r for r in results}
        for idx, expected in [(528, "Python,"), (529, "Java,"), (530, "C,"), (531, "Bash")]:
            assert idx in by_index, f"word {expected} at index {idx} never reached the model"
            assert by_index[idx]["token"] == expected
            assert by_index[idx]["label"] == "B-PROGRAMMING_LANGUAGE"

    def test_every_word_of_a_long_document_gets_exactly_one_prediction(
        self, monkeypatch, patched_serving, label_list
    ):
        tokens = [f"w{i}" for i in range(900)]
        session = _fake_session(lambda pos: (1, 5.0), len(label_list))
        monkeypatch.setattr(
            inference_service.model_cache,
            "get",
            lambda mid: type("C", (), {"model": {"session": session}})(),
        )

        results = inference_service._infer_with_onnx(tokens, "t1")

        indices = [r["word_index"] for r in results]
        assert indices == sorted(indices), "predictions must stay in document order"
        assert len(indices) == len(set(indices)), "no word may be emitted twice"
        assert set(indices) == set(range(900)), "every word must be covered"

    def test_short_document_output_is_unchanged(self, monkeypatch, patched_serving, label_list):
        """Regression guard for documents that already fit in one window: single
        session call, same tokens, same order, same labels, `O` still filtered out."""
        tokens = ["Acme", "Corp", "uses", "Python", "daily"]
        target = _positions_of_word(tokens, 3)

        calls = {"n": 0}

        class FakeSession:
            def get_inputs(self):
                return [_FakeInput("input_ids"), _FakeInput("attention_mask")]

            def run(self, output_names, inputs):
                calls["n"] += 1
                seq_len = inputs["input_ids"].shape[1]
                logits = np.zeros((1, seq_len, len(label_list)), dtype=np.float32)
                for pos in range(seq_len):
                    logits[0, pos, 1 if pos in target else 0] = 5.0
                return [logits]

        session = FakeSession()
        monkeypatch.setattr(
            inference_service.model_cache,
            "get",
            lambda mid: type("C", (), {"model": {"session": session}})(),
        )

        results = inference_service._infer_with_onnx(tokens, "t1")

        assert calls["n"] == 1, "a document under the limit must still be one pass"
        assert [r["token"] for r in results] == ["Python"]
        assert results[0]["label"] == "B-PROGRAMMING_LANGUAGE"
        assert results[0]["word_index"] == 3


class TestOverlapDeduplication:
    def test_overlap_word_is_emitted_once_and_prefers_the_interior_window(
        self, monkeypatch, patched_serving, label_list
    ):
        """A word in the overlap region is scored by two windows. The window where it
        sat further from an edge wins, because edge tokens see truncated context."""
        tokens = [f"w{i}" for i in range(600)]

        calls = {"n": 0}

        def alternating(pos):
            # First window labels everything B-, second window labels everything I-.
            return (1, 5.0) if calls["n"] == 0 else (2, 9.0)

        class FakeSession:
            def get_inputs(self):
                return [_FakeInput("input_ids"), _FakeInput("attention_mask")]

            def run(self, output_names, inputs):
                seq_len = inputs["input_ids"].shape[1]
                logits = np.zeros((1, seq_len, len(label_list)), dtype=np.float32)
                for pos in range(seq_len):
                    chosen, score = alternating(pos)
                    logits[0, pos, chosen] = score
                calls["n"] += 1
                return [logits]

        session = FakeSession()
        monkeypatch.setattr(
            inference_service.model_cache,
            "get",
            lambda mid: type("C", (), {"model": {"session": session}})(),
        )

        results = inference_service._infer_with_onnx(tokens, "t1")

        indices = [r["word_index"] for r in results]
        assert len(indices) == len(set(indices)), "overlap must not duplicate a word"

        budget, overlap = _window_geometry()
        windows = _build_windows(_real_piece_counts(tokens), budget, overlap)
        assert len(windows) >= 2
        (w0_start, w0_end), (w1_start, w1_end) = windows[0], windows[1]
        by_index = {r["word_index"]: r for r in results}

        for gi in range(w1_start, w0_end):
            dist_first = min(gi - w0_start, (w0_end - 1) - gi)
            dist_second = min(gi - w1_start, (w1_end - 1) - gi)
            winner = "B-PROGRAMMING_LANGUAGE" if dist_first > dist_second else "I-PROGRAMMING_LANGUAGE"
            assert by_index[gi]["label"] == winner, (
                f"word {gi} in overlap should come from the window that held it "
                f"further from an edge"
            )

    def test_word_at_a_window_seam_is_not_duplicated_in_the_response(
        self, monkeypatch, patched_serving, label_list
    ):
        tokens = [f"w{i}" for i in range(1500)]
        session = _fake_session(lambda pos: (1, 5.0), len(label_list))
        monkeypatch.setattr(
            inference_service.model_cache,
            "get",
            lambda mid: type("C", (), {"model": {"session": session}})(),
        )

        results = inference_service._infer_with_onnx(tokens, "t1")
        seen = [r["word_index"] for r in results]
        assert len(seen) == len(set(seen))
        assert len(seen) == 1500


class TestOversizedWordIsLoudNotSilent:
    def test_word_longer_than_the_window_logs_a_warning(
        self, monkeypatch, patched_serving, label_list, caplog
    ):
        # BERT's WordPiece caps a word at max_input_chars_per_word (100) and falls back
        # to a single [UNK], so no realistic word exceeds a 400-piece budget. Shrink the
        # window instead — the point is that an unfittable input is reported, not that
        # such an input is common.
        monkeypatch.setattr(settings, "inference_window_size", 2)
        monkeypatch.setattr(settings, "inference_window_overlap", 1)
        tokens = ["Acme", "internationalization", "Corp"]
        assert max(_real_piece_counts(tokens)) > 2

        session = _fake_session(lambda pos: (0, 5.0), len(label_list))
        monkeypatch.setattr(
            inference_service.model_cache,
            "get",
            lambda mid: type("C", (), {"model": {"session": session}})(),
        )

        with caplog.at_level("WARNING", logger=inference_service.__name__):
            inference_service._infer_with_onnx(tokens, "t1")

        assert any("longer than the" in rec.message for rec in caplog.records), (
            "an input the windower still cannot fit must be reported, not truncated silently"
        )

    def test_pdf_bullet_glyphs_do_not_trigger_a_truncation_warning(
        self, monkeypatch, patched_serving, label_list, caplog
    ):
        """U+F0B7 is a private-use bullet that PDF extraction emits constantly. BERT's
        tokenizer normalizes it to zero WordPieces, so it is unlabelable rather than
        truncated — counting it as dropped coverage would cry wolf on nearly every
        real document and drown out genuine data loss."""
        tokens = ["Skills", "", "Python", "", "Java"]
        assert 0 in _real_piece_counts(tokens)

        session = _fake_session(lambda pos: (0, 5.0), len(label_list))
        monkeypatch.setattr(
            inference_service.model_cache,
            "get",
            lambda mid: type("C", (), {"model": {"session": session}})(),
        )

        with caplog.at_level("WARNING", logger=inference_service.__name__):
            inference_service._infer_with_onnx(tokens, "t1")

        assert not [r for r in caplog.records if r.levelname == "WARNING"], (
            f"unexpected warning(s): {[r.message for r in caplog.records]}"
        )
