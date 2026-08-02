"""Confidence scoring helper interface."""

from abc import ABC, abstractmethod

from code.data.models import Prediction


class ConfidenceScorer(ABC):
    """Abstract interface for confidence score adjustment and validation."""

    @abstractmethod
    def score(
        self,
        raw_confidence: float,
        *,
        has_evidence: bool = False,
        rule_matched: bool = False,
    ) -> float:
        """Compute a normalized confidence score.

        Args:
            raw_confidence: Initial confidence from the decision source.
            has_evidence: Whether supporting evidence messages exist.
            rule_matched: Whether a deterministic rule matched.

        Returns:
            Normalized confidence in ``[0.0, 1.0]``.
        """
        # TODO: Implement in concrete scorer.

    @abstractmethod
    def clamp(self, confidence: float) -> float:
        """Clamp a confidence value to the valid range.

        Args:
            confidence: Raw confidence value.

        Returns:
            Confidence clamped to ``[0.0, 1.0]``.
        """
        # TODO: Implement in concrete scorer.

    @abstractmethod
    def adjust(self, prediction: Prediction, adjustment: float) -> Prediction:
        """Return a prediction with an adjusted confidence score.

        Args:
            prediction: Original prediction.
            adjustment: Delta to apply to confidence.

        Returns:
            New prediction with updated confidence.
        """
        # TODO: Implement in concrete scorer.
