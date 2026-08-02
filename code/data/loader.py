"""CSV dataset loading utilities."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import pandas as pd

from code.utils.logger import get_logger

_logger = get_logger("data.loader")

REQUIRED_DATASET_FILES: Final[tuple[str, ...]] = (
    "messages.csv",
    "users.csv",
    "groups.csv",
    "group_members.csv",
    "business_accounts.csv",
    "user_business_history.csv",
    "message_history.csv",
    "message_events.csv",
    "daily_notification_summary.csv",
    "images.csv",
    "sample_messages.csv",
)

_FILENAME_TO_FIELD: Final[dict[str, str]] = {
    "messages.csv": "messages",
    "users.csv": "users",
    "groups.csv": "groups",
    "group_members.csv": "group_members",
    "business_accounts.csv": "business_accounts",
    "user_business_history.csv": "user_business_history",
    "message_history.csv": "message_history",
    "message_events.csv": "message_events",
    "daily_notification_summary.csv": "daily_notification_summary",
    "images.csv": "images",
    "sample_messages.csv": "sample_messages",
}


class DatasetLoadError(Exception):
    """Base exception for dataset loading failures."""


class MissingDatasetFileError(DatasetLoadError):
    """Raised when a required dataset file is absent."""


class EmptyDatasetError(DatasetLoadError):
    """Raised when a dataset file contains no rows."""


class InvalidDatasetDirectoryError(DatasetLoadError):
    """Raised when the configured dataset directory is invalid."""


@dataclass(frozen=True)
class Dataset:
    """Structured container for all loaded CSV datasets.

    Each attribute holds the raw dataframe for a known dataset file.
    Additional CSV files discovered in the directory are stored in
    ``additional`` keyed by filename.
    """

    messages: pd.DataFrame
    users: pd.DataFrame
    groups: pd.DataFrame
    group_members: pd.DataFrame
    business_accounts: pd.DataFrame
    user_business_history: pd.DataFrame
    message_history: pd.DataFrame
    message_events: pd.DataFrame
    daily_notification_summary: pd.DataFrame
    images: pd.DataFrame
    sample_messages: pd.DataFrame
    additional: dict[str, pd.DataFrame] = field(default_factory=dict)

    def as_dict(self) -> dict[str, pd.DataFrame]:
        """Return all known datasets keyed by CSV filename.

        Returns:
            Mapping of filename to dataframe, including additional files.
        """
        known = {
            "messages.csv": self.messages,
            "users.csv": self.users,
            "groups.csv": self.groups,
            "group_members.csv": self.group_members,
            "business_accounts.csv": self.business_accounts,
            "user_business_history.csv": self.user_business_history,
            "message_history.csv": self.message_history,
            "message_events.csv": self.message_events,
            "daily_notification_summary.csv": self.daily_notification_summary,
            "images.csv": self.images,
            "sample_messages.csv": self.sample_messages,
        }
        return {**known, **self.additional}


class DatasetLoader:
    """Loads CSV datasets from disk.

    Responsible ONLY for loading CSV files. No routing logic.
    """

    def __init__(self, data_dir: Path) -> None:
        """Initialize the loader with a data directory.

        Args:
            data_dir: Root directory containing CSV dataset files.
        """
        self._data_dir = data_dir

    @property
    def data_dir(self) -> Path:
        """Return the configured dataset directory."""
        return self._data_dir

    def load(self) -> Dataset:
        """Load every CSV in the dataset directory into a Dataset container.

        All required files must be present. Any extra ``*.csv`` files found
        in the directory are included under ``Dataset.additional``.

        Returns:
            Populated Dataset instance.

        Raises:
            InvalidDatasetDirectoryError: If the data directory does not exist.
            MissingDatasetFileError: If a required CSV file is missing.
            EmptyDatasetError: If a CSV file contains zero rows.
        """
        self._ensure_data_dir_exists()
        self._ensure_required_files_present()

        frames: dict[str, pd.DataFrame] = {}
        for csv_path in self.list_csv_files():
            frames[csv_path.name] = self._load_dataframe(csv_path)

        return self._build_dataset(frames)

    def load_csv(self, filename: str) -> pd.DataFrame:
        """Load a single CSV file into a dataframe.

        Args:
            filename: Name of the CSV file within the data directory.

        Returns:
            Raw dataframe with original column names preserved.

        Raises:
            MissingDatasetFileError: If the requested CSV file does not exist.
            EmptyDatasetError: If the CSV file contains zero rows.
        """
        path = self._resolve_file_path(filename)
        return self._load_dataframe(path)

    def load_all(self, filenames: list[str]) -> dict[str, pd.DataFrame]:
        """Load multiple CSV files by name.

        Args:
            filenames: List of CSV filenames to load.

        Returns:
            Mapping of filename to loaded dataframe.
        """
        return {name: self.load_csv(name) for name in filenames}

    def list_csv_files(self) -> list[Path]:
        """List all CSV files in the data directory.

        Returns:
            Sorted list of CSV file paths.
        """
        if not self._data_dir.is_dir():
            return []
        return sorted(self._data_dir.glob("*.csv"))

    def _ensure_data_dir_exists(self) -> None:
        """Verify the configured dataset directory exists.

        Raises:
            InvalidDatasetDirectoryError: If the directory is missing.
        """
        if not self._data_dir.is_dir():
            raise InvalidDatasetDirectoryError(
                f"Dataset directory not found or not a directory: {self._data_dir}"
            )

    def _ensure_required_files_present(self) -> None:
        """Verify every required dataset file is present.

        Raises:
            MissingDatasetFileError: If any required file is absent.
        """
        missing = [
            name
            for name in REQUIRED_DATASET_FILES
            if not (self._data_dir / name).is_file()
        ]
        if missing:
            formatted = ", ".join(sorted(missing))
            raise MissingDatasetFileError(
                f"Missing required dataset file(s) in {self._data_dir}: {formatted}"
            )

    def _resolve_file_path(self, filename: str) -> Path:
        """Resolve and validate a CSV file path within the data directory.

        Args:
            filename: CSV filename relative to the data directory.

        Returns:
            Absolute path to the CSV file.

        Raises:
            MissingDatasetFileError: If the file does not exist.
        """
        path = self._data_dir / filename
        if not path.is_file():
            raise MissingDatasetFileError(
                f"Dataset file not found: {path} "
                f"(expected inside {self._data_dir})"
            )
        return path

    def _load_dataframe(self, path: Path) -> pd.DataFrame:
        """Read a CSV file into a dataframe without modifying its contents.

        Args:
            path: Path to the CSV file.

        Returns:
            Loaded dataframe with original column names preserved.

        Raises:
            EmptyDatasetError: If the file contains zero data rows.
        """
        dataframe = pd.read_csv(path, na_filter=False)
        self._validate_not_empty(dataframe, path.name)
        _logger.info(
            "Loaded dataset %s (%d rows, %d columns)",
            path.name,
            len(dataframe),
            len(dataframe.columns),
        )
        return dataframe

    @staticmethod
    def _validate_not_empty(dataframe: pd.DataFrame, filename: str) -> None:
        """Ensure a dataframe contains at least one row.

        Args:
            dataframe: Loaded dataframe to validate.
            filename: Source filename for error reporting.

        Raises:
            EmptyDatasetError: If the dataframe has no rows.
        """
        if dataframe.empty:
            raise EmptyDatasetError(
                f"Dataset file contains no rows: {filename}"
            )

    @staticmethod
    def _build_dataset(frames: dict[str, pd.DataFrame]) -> Dataset:
        """Assemble a Dataset from loaded dataframes.

        Args:
            frames: Mapping of CSV filename to loaded dataframe.

        Returns:
            Structured Dataset instance.
        """
        known_fields = {
            field_name: frames[filename]
            for filename, field_name in _FILENAME_TO_FIELD.items()
        }
        additional = {
            name: frame
            for name, frame in frames.items()
            if name not in _FILENAME_TO_FIELD
        }
        return Dataset(**known_fields, additional=additional)
