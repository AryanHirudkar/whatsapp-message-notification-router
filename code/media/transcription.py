"""Speech transcription provider interface."""

from abc import ABC, abstractmethod
from pathlib import Path


class TranscriptionResult:
    """Structured result from a transcription operation."""

    def __init__(
        self,
        text: str,
        language: str | None = None,
        confidence: float | None = None,
    ) -> None:
        """Initialize a transcription result.

        Args:
            text: Transcribed text content.
            language: Detected or specified language code.
            confidence: Optional aggregate confidence score.
        """
        self.text = text
        self.language = language
        self.confidence = confidence


class TranscriptionProvider(ABC):
    """Abstract interface for speech-to-text providers."""

    @abstractmethod
    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        """Transcribe speech from an audio file.

        Args:
            audio_path: Path to the source audio file.

        Returns:
            Transcription result.
        """
        # TODO: Implement in concrete provider.

    @abstractmethod
    def transcribe_bytes(self, audio_data: bytes) -> TranscriptionResult:
        """Transcribe speech from raw audio bytes.

        Args:
            audio_data: Raw audio file contents.

        Returns:
            Transcription result.
        """
        # TODO: Implement in concrete provider.
