"""Audio loading utilities."""

from pathlib import Path

from code.config import Config
from code.utils.logger import get_logger

_logger = get_logger("media.voice_processor")


class VoiceProcessor:
    """Loads voice note files for downstream transcription.

    Audio loading only. No transcription.
    """

    def __init__(self, config: Config) -> None:
        """Initialize the voice processor.

        Args:
            config: Application configuration.
        """
        self._config = config

    def load(self, file_path: Path) -> bytes:
        """Load raw audio bytes from disk.

        Args:
            file_path: Path to the audio file.

        Returns:
            Raw audio file contents.

        Raises:
            FileNotFoundError: If the audio file does not exist.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        data = file_path.read_bytes()
        _logger.debug("Loaded audio %s (%.2f KB)", file_path.name, len(data) / 1024)
        return data

    def validate(self, file_path: Path) -> bool:
        """Check whether an audio file is within configured constraints.

        Args:
            file_path: Path to the audio file.

        Returns:
            ``True`` if the audio file exists and passes validation.
        """
        # TODO: Validate duration against config.max_audio_duration_sec.
        return file_path.exists()
