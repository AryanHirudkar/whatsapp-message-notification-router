"""OCR provider interface."""

from abc import ABC, abstractmethod
from pathlib import Path


class OCRResult:
    """Structured result from an OCR operation."""

    def __init__(self, text: str, confidence: float | None = None) -> None:
        """Initialize an OCR result.

        Args:
            text: Extracted text content.
            confidence: Optional aggregate confidence score.
        """
        self.text = text
        self.confidence = confidence


class OCRProvider(ABC):
    """Abstract interface for optical character recognition providers."""

    @abstractmethod
    def extract_text(self, image_path: Path) -> OCRResult:
        """Extract text from an image file.

        Args:
            image_path: Path to the source image.

        Returns:
            OCR extraction result.
        """
        # TODO: Implement in concrete provider.

    @abstractmethod
    def extract_text_from_bytes(self, image_data: bytes) -> OCRResult:
        """Extract text from raw image bytes.

        Args:
            image_data: Raw image file contents.

        Returns:
            OCR extraction result.
        """
        # TODO: Implement in concrete provider.
