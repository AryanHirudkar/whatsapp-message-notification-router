"""Output validation interface."""

from abc import ABC, abstractmethod

from code.data.models import Prediction


class ValidationResult:
    """Result of output validation."""

    def __init__(self, is_valid: bool, errors: list[str] | None = None) -> None:
        """Initialize a validation result.

        Args:
            is_valid: Whether validation passed.
            errors: List of validation error messages.
        """
        self.is_valid = is_valid
        self.errors = errors or []


class OutputValidator(ABC):
    """Abstract interface for validating routing predictions."""

    @abstractmethod
    def validate(self, prediction: Prediction) -> ValidationResult:
        """Validate a single prediction against the output schema.

        Args:
            prediction: Routing prediction to validate.

        Returns:
            Validation result with any error messages.
        """
        # TODO: Implement in concrete validator.

    @abstractmethod
    def validate_batch(self, predictions: list[Prediction]) -> ValidationResult:
        """Validate a batch of predictions.

        Args:
            predictions: Predictions to validate.

        Returns:
            Aggregate validation result.
        """
        # TODO: Implement in concrete validator.
