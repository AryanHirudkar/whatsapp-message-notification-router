"""Evaluation metric dataclasses and interfaces."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class EvaluationMetrics:
    """Aggregate evaluation metrics for routing predictions."""

    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    per_action_metrics: dict[str, dict[str, float]] = field(default_factory=dict)
    total_samples: int = 0
    correct_samples: int = 0


class MetricsCalculator(ABC):
    """Abstract interface for computing evaluation metrics."""

    @abstractmethod
    def compute(
        self,
        predicted_actions: list[str],
        true_actions: list[str],
    ) -> EvaluationMetrics:
        """Compute metrics from parallel action label lists.

        Args:
            predicted_actions: Predicted action labels.
            true_actions: Ground truth action labels.

        Returns:
            Computed evaluation metrics.
        """
        # TODO: Implement in concrete calculator.

    @abstractmethod
    def compute_per_action(
        self,
        predicted_actions: list[str],
        true_actions: list[str],
    ) -> dict[str, dict[str, float]]:
        """Compute per-action precision, recall, and F1.

        Args:
            predicted_actions: Predicted action labels.
            true_actions: Ground truth action labels.

        Returns:
            Mapping of action name to metric dictionary.
        """
        # TODO: Implement in concrete calculator.
