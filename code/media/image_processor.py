"""Image loading utilities."""

from abc import ABC, abstractmethod
from pathlib import Path

from code.config import Config
from code.utils.logger import get_logger

_logger = get_logger("media.image_processor")


class ImageProcessor:
    """Loads image files for downstream OCR processing.

    Image loading only. No OCR.
    """

    def __init__(self, config: Config) -> None:
        """Initialize the image processor.

        Args:
            config: Application configuration.
        """
        self._config = config

    def load(self, file_path: Path) -> bytes:
        """Load raw image bytes from disk.

        Args:
            file_path: Path to the image file.

        Returns:
            Raw image file contents.

        Raises:
            FileNotFoundError: If the image file does not exist.
            ValueError: If the image exceeds configured size limits.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Image not found: {file_path}")

        data = file_path.read_bytes()
        size_mb = len(data) / (1024 * 1024)
        if size_mb > self._config.max_image_size_mb:
            raise ValueError(
                f"Image exceeds max size ({size_mb:.2f}MB > "
                f"{self._config.max_image_size_mb}MB): {file_path}"
            )

        _logger.debug("Loaded image %s (%.2f MB)", file_path.name, size_mb)
        return data

    def validate(self, file_path: Path) -> bool:
        """Check whether an image file is within configured constraints.

        Args:
            file_path: Path to the image file.

        Returns:
            ``True`` if the image is valid, ``False`` otherwise.
        """
        # TODO: Add MIME-type and dimension validation when spec is defined.
        try:
            self.load(file_path)
            return True
        except (FileNotFoundError, ValueError):
            return False
