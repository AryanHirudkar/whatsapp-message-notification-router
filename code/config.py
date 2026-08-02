"""Centralized application configuration."""

from dataclasses import dataclass, replace
from pathlib import Path

# Module-level constants — single source for defaults. No magic numbers elsewhere.
MAX_HISTORY_MESSAGES: int = 50
MAX_EVIDENCE_MESSAGES: int = 10
MAX_LLM_RETRIES: int = 3
MAX_IMAGE_SIZE_MB: float = 10.0
MAX_AUDIO_DURATION_SEC: float = 300.0
DEFAULT_CONFIDENCE: float = 0.0
ENABLE_MEDIA: bool = True
ENABLE_RULE_ENGINE: bool = True
ENABLE_EVALUATION: bool = False


@dataclass(frozen=True)
class Config:
    """Application-wide configuration values.

    All tunable parameters must be defined here. No magic numbers elsewhere.
    """

    max_history_messages: int = MAX_HISTORY_MESSAGES
    max_evidence_messages: int = MAX_EVIDENCE_MESSAGES
    max_llm_retries: int = MAX_LLM_RETRIES
    max_image_size_mb: float = MAX_IMAGE_SIZE_MB
    max_audio_duration_sec: float = MAX_AUDIO_DURATION_SEC
    default_confidence: float = DEFAULT_CONFIDENCE
    enable_media: bool = ENABLE_MEDIA
    enable_rule_engine: bool = ENABLE_RULE_ENGINE
    enable_evaluation: bool = ENABLE_EVALUATION
    data_dir: Path = Path("dataset")
    output_path: Path = Path("output.csv")
    log_level: str = "INFO"
    log_file: Path | None = None


def load_config(
    data_dir: Path | None = None,
    output_path: Path | None = None,
) -> Config:
    """Load and return application configuration.

    Args:
        data_dir: Optional override for the input data directory.
        output_path: Optional override for the output CSV path.

    Returns:
        Resolved configuration object.
    """
    overrides: dict[str, object] = {}
    if data_dir is not None:
        overrides["data_dir"] = data_dir
    if output_path is not None:
        overrides["output_path"] = output_path
    # TODO: Support environment-variable overrides when required.
    return replace(Config(), **overrides)
