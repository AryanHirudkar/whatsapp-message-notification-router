"""Safety checks for routing inputs and outputs."""

from abc import ABC, abstractmethod

from code.data.models import MessageContext, Prediction


class SafetyChecker(ABC):
    """Abstract interface for safety validation."""

    @abstractmethod
    def is_safe_context(self, context: MessageContext) -> bool:
        """Determine whether a message context is safe to process.

        Args:
            context: Assembled message context.

        Returns:
            ``True`` if the context passes safety checks.
        """
        # TODO: Implement in concrete safety checker.

    @abstractmethod
    def is_safe_prediction(self, prediction: Prediction) -> bool:
        """Determine whether a prediction is safe to emit.

        Args:
            prediction: Routing prediction.

        Returns:
            ``True`` if the prediction passes safety checks.
        """
        # TODO: Implement in concrete safety checker.

    @abstractmethod
    def sanitize_reason(self, reason: str) -> str:
        """Sanitize a prediction reason string for output.

        Args:
            reason: Raw reason text.

        Returns:
            Sanitized reason string.
        """
        # TODO: Implement in concrete safety checker.
