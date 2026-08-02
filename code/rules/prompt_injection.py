"""Prompt injection detection interface."""

from abc import ABC, abstractmethod

from code.data.models import MessageContext


class InjectionDetectionResult:
    """Result of a prompt injection scan."""

    def __init__(
        self,
        is_injection: bool,
        confidence: float = 0.0,
        matched_patterns: list[str] | None = None,
    ) -> None:
        """Initialize a detection result.

        Args:
            is_injection: Whether injection was detected.
            confidence: Detection confidence score.
            matched_patterns: Names of matched detection patterns.
        """
        self.is_injection = is_injection
        self.confidence = confidence
        self.matched_patterns = matched_patterns or []


class PromptInjectionDetector(ABC):
    """Abstract interface for detecting prompt injection attempts."""

    @abstractmethod
    def detect(self, text: str) -> InjectionDetectionResult:
        """Scan text for prompt injection patterns.

        Args:
            text: Raw message or prompt text.

        Returns:
            Detection result.
        """
        # TODO: Implement in concrete detector.

    @abstractmethod
    def detect_context(self, context: MessageContext) -> InjectionDetectionResult:
        """Scan an entire message context for injection attempts.

        Args:
            context: Assembled message context.

        Returns:
            Detection result.
        """
        # TODO: Implement in concrete detector.
