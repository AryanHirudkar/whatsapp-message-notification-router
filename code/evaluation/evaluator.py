"""Evaluation orchestration interface."""

from abc import ABC, abstractmethod
from pathlib import Path

from code.data.models import Prediction
from code.evaluation.metrics import EvaluationMetrics


class Evaluator(ABC):
    """Abstract interface for evaluating routing predictions.

    No implementation.
    """

    @abstractmethod
    def evaluate(
        self,
        predictions: list[Prediction],
        ground_truth_path: Path,
    ) -> EvaluationMetrics:
        """Evaluate predictions against ground truth labels.

        Args:
            predictions: Model predictions to evaluate.
            ground_truth_path: Path to ground truth CSV file.

        Returns:
            Computed evaluation metrics.
        """
        # TODO: Implement in concrete evaluator.

    @abstractmethod
    def evaluate_file(
        self,
        predictions_path: Path,
        ground_truth_path: Path,
    ) -> EvaluationMetrics:
        """Evaluate predictions file against ground truth file.

        Args:
            predictions_path: Path to predictions CSV.
            ground_truth_path: Path to ground truth CSV.

        Returns:
            Computed evaluation metrics.
        """
        # TODO: Implement in concrete evaluator.
