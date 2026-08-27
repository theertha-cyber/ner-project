"""The processing mode a batch extraction run executes under.

The mode is chosen by the caller, validated by the API, and carried to the worker as a
task argument. It is deliberately *not* read from settings by the worker: a run's
behaviour is fixed at enqueue time, so a configuration change while a run is queued
cannot make the recorded mode disagree with what actually happened."""

from enum import Enum

from src.shared.config import settings


class ProcessingMode(str, Enum):
    BERT_ONLY = "bert_only"
    BERT_LLM_POSTPROCESS = "bert_llm_postprocess"


# Post-processing costs tokens, adds an external dependency to extraction, and has not
# yet cleared the evaluation gate. A default that silently spends money is the wrong
# default, so a caller that says nothing gets the pipeline that exists today.
DEFAULT_PROCESSING_MODE = ProcessingMode.BERT_ONLY


def is_postprocessing_configured() -> bool:
    """Whether this deployment can run the post-processing stage at all.

    Requires both the explicit toggle and a chat deployment to call. A deployment
    missing either rejects the mode outright rather than silently downgrading — a
    caller who asked for post-processing and got BERT-only without being told would
    have no way to know the run's data is not what they requested."""
    return bool(settings.postprocess_enabled and settings.azure_openai_chat_deployment)
