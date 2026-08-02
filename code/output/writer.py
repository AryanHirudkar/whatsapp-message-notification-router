"""CSV output writing utilities."""

import csv
from pathlib import Path

from code.data.models import Prediction
from code.schemas import OUTPUT_COLUMNS
from code.utils.helpers import join_evidence_ids
from code.utils.logger import get_logger

_logger = get_logger("output.writer")


class OutputWriter:
    """Writes routing predictions to output CSV."""

    def __init__(self, output_path: Path) -> None:
        """Initialize the writer.

        Args:
            output_path: Destination CSV file path.
        """
        self._output_path = output_path

    def write(self, predictions: list[Prediction]) -> None:
        """Write predictions to the output CSV file.

        Args:
            predictions: Routing predictions to serialize.
        """
        self._output_path.parent.mkdir(parents=True, exist_ok=True)

        with self._output_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(OUTPUT_COLUMNS))
            writer.writeheader()
            for prediction in predictions:
                writer.writerow(self._prediction_to_row(prediction))

        _logger.info("Wrote %d predictions to %s", len(predictions), self._output_path)

    @staticmethod
    def _prediction_to_row(prediction: Prediction) -> dict[str, str | float]:
        """Convert a Prediction to an output row dictionary.

        Args:
            prediction: Prediction to convert.

        Returns:
            Row dictionary matching OUTPUT_COLUMNS.
        """
        return {
            "message_id": prediction.message_id,
            "action": prediction.action.value,
            "message_type": prediction.message_type.value,
            "reason": prediction.reason,
            "confidence": prediction.confidence,
            "evidence_message_ids": join_evidence_ids(
                list(prediction.evidence_message_ids)
            ),
        }
