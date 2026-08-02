"""In-memory index construction for efficient lookups."""

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Final

import pandas as pd

from code.data.loader import Dataset
from code.data.models import (
    Business,
    Group,
    MediaReference,
    Message,
    User,
)
from code.schemas import ConversationType, MediaType
from code.utils.logger import get_logger

_logger = get_logger("data.indexer")

Row = pd.Series

# Expected primary-key columns per dataset (must match CSV headers exactly).
USER_ID_COLUMN: Final[str] = "user_id"
GROUP_ID_COLUMN: Final[str] = "group_id"
BUSINESS_ID_COLUMN: Final[str] = "business_id"
MESSAGE_ID_COLUMN: Final[str] = "message_id"
IMAGE_ID_COLUMN: Final[str] = "image_id"
SENDER_ID_COLUMN: Final[str] = "sender_user_id"
RECEIVER_ID_COLUMN: Final[str] = "receiver_id"


class IndexBuildError(Exception):
    """Base exception for index construction failures."""


class MissingIndexColumnError(IndexBuildError):
    """Raised when a required index column is absent from a dataset."""


@dataclass(frozen=True)
class IndexStore:
    """Strongly typed container for all in-memory dataset indexes.

    Each index maps lookup keys to original dataframe rows (``pd.Series``).
    Row values are never modified; indexes only organize references to them.
    """

    users_by_id: dict[str, Row]
    groups_by_id: dict[str, Row]
    businesses_by_id: dict[str, Row]
    members_by_group: dict[str, list[Row]]
    business_history_by_user: dict[str, list[Row]]
    history_by_user: dict[str, list[Row]]
    events_by_message: dict[str, list[Row]]
    events_by_user: dict[str, list[Row]]
    notifications_by_user: dict[str, list[Row]]
    images_by_id: dict[str, Row]
    messages_by_sender: dict[str, list[Row]]
    messages_by_group: dict[str, list[Row]]
    messages_by_business: dict[str, list[Row]]


class MessageIndexer:
    """Builds efficient in-memory indexes from loaded datasets.

    No reasoning or routing decisions.
    """

    def __init__(self) -> None:
        """Initialize an empty indexer."""
        self._store: IndexStore | None = None
        self._messages_in_order: list[Row] = []

    @property
    def store(self) -> IndexStore:
        """Return the built index store.

        Returns:
            Populated IndexStore instance.

        Raises:
            RuntimeError: If ``build`` has not been called yet.
        """
        if self._store is None:
            raise RuntimeError("MessageIndexer has not been built. Call build() first.")
        return self._store

    def build(self, dataset: Dataset) -> IndexStore:
        """Build all indexes from a loaded dataset.

        Args:
            dataset: Fully loaded dataset from ``DatasetLoader``.

        Returns:
            Populated IndexStore instance.
        """
        users_by_id = _build_unique_index(
            dataset.users,
            USER_ID_COLUMN,
            index_name="users_by_id",
        )
        groups_by_id = _build_unique_index(
            dataset.groups,
            GROUP_ID_COLUMN,
            index_name="groups_by_id",
        )
        businesses_by_id = _build_unique_index(
            dataset.business_accounts,
            BUSINESS_ID_COLUMN,
            index_name="businesses_by_id",
        )
        members_by_group = _build_list_index(
            dataset.group_members,
            GROUP_ID_COLUMN,
            index_name="members_by_group",
        )
        business_history_by_user = _build_list_index(
            dataset.user_business_history,
            USER_ID_COLUMN,
            index_name="business_history_by_user",
        )
        history_by_user = _build_list_index(
            dataset.message_history,
            USER_ID_COLUMN,
            index_name="history_by_user",
        )
        events_by_message, events_by_user = _build_message_event_indexes(
            dataset.message_events,
        )
        notifications_by_user = _build_list_index(
            dataset.daily_notification_summary,
            USER_ID_COLUMN,
            index_name="notifications_by_user",
        )
        images_by_id = _build_unique_index(
            dataset.images,
            IMAGE_ID_COLUMN,
            index_name="images_by_id",
        )
        messages_by_sender, messages_by_group, messages_by_business = (
            _build_message_indexes(dataset.messages)
        )
        self._messages_in_order = [
            dataset.messages.iloc[position]
            for position in range(len(dataset.messages))
        ]

        self._store = IndexStore(
            users_by_id=users_by_id,
            groups_by_id=groups_by_id,
            businesses_by_id=businesses_by_id,
            members_by_group=members_by_group,
            business_history_by_user=business_history_by_user,
            history_by_user=history_by_user,
            events_by_message=events_by_message,
            events_by_user=events_by_user,
            notifications_by_user=notifications_by_user,
            images_by_id=images_by_id,
            messages_by_sender=messages_by_sender,
            messages_by_group=messages_by_group,
            messages_by_business=messages_by_business,
        )
        return self._store

    def get_user(self, user_id: str) -> User | None:
        """Retrieve a user by identifier.

        Args:
            user_id: Unique user identifier.

        Returns:
            Matching user or ``None``.
        """
        row = self.store.users_by_id.get(user_id)
        if row is None:
            return None
        return _row_to_user(row)

    def get_group(self, group_id: str) -> Group | None:
        """Retrieve a group by identifier.

        Args:
            group_id: Unique group identifier.

        Returns:
            Matching group or ``None``.
        """
        row = self.store.groups_by_id.get(group_id)
        if row is None:
            return None
        return _row_to_group(row)

    def get_business(self, business_id: str) -> Business | None:
        """Retrieve a business by identifier.

        Args:
            business_id: Unique business identifier.

        Returns:
            Matching business or ``None``.
        """
        row = self.store.businesses_by_id.get(business_id)
        if row is None:
            return None
        return _row_to_business(row)

    def get_messages_for_sender(self, sender_user_id: str) -> list[Message]:
        """Retrieve messages sent by a sender.

        Args:
            sender_user_id: Sender user identifier.

        Returns:
            Messages from the sender in original dataset order within the bucket.
        """
        rows = self.store.messages_by_sender.get(sender_user_id, [])
        return [_row_to_message(row) for row in rows]

    @property
    def all_messages(self) -> list[Message]:
        """Return all messages in original dataset order.

        Returns:
            List of all messages from ``messages.csv`` row order.
        """
        return [_row_to_message(row) for row in self._messages_in_order]


def _require_column(dataframe: pd.DataFrame, column: str, dataset_name: str) -> None:
    """Ensure a dataframe contains a required index column.

    Args:
        dataframe: Source dataframe.
        column: Required column name.
        dataset_name: Dataset label for error reporting.

    Raises:
        MissingIndexColumnError: If the column is absent.
    """
    if column not in dataframe.columns:
        raise MissingIndexColumnError(
            f"Cannot build index: column '{column}' missing from {dataset_name}"
        )


def _row_key(row: Row, column: str) -> str:
    """Extract a string lookup key from a row without coercion.

    Args:
        row: Source dataframe row.
        column: Column containing the key value.

    Returns:
        String representation of the key exactly as stored in the row.
    """
    return str(row[column])


def _build_unique_index(
    dataframe: pd.DataFrame,
    key_column: str,
    *,
    index_name: str,
) -> dict[str, Row]:
    """Build a one-to-one index from a dataframe.

    Args:
        dataframe: Source dataset dataframe.
        key_column: Column used as the lookup key.
        index_name: Index name used for logging and errors.

    Returns:
        Mapping of key to row series.
    """
    _require_column(dataframe, key_column, index_name)
    index: dict[str, Row] = {}
    for position in range(len(dataframe)):
        row = dataframe.iloc[position]
        index[_row_key(row, key_column)] = row
    _log_index_completed(index_name, len(index))
    return index


def _build_list_index(
    dataframe: pd.DataFrame,
    key_column: str,
    *,
    index_name: str,
) -> dict[str, list[Row]]:
    """Build a one-to-many index preserving dataframe row order.

    Args:
        dataframe: Source dataset dataframe.
        key_column: Column used as the lookup key.
        index_name: Index name used for logging and errors.

    Returns:
        Mapping of key to ordered list of row series.
    """
    _require_column(dataframe, key_column, index_name)
    index: dict[str, list[Row]] = defaultdict(list)
    for position in range(len(dataframe)):
        row = dataframe.iloc[position]
        index[_row_key(row, key_column)].append(row)
    completed = dict(index)
    _log_index_completed(index_name, len(completed))
    return completed


def _build_message_event_indexes(
    dataframe: pd.DataFrame,
) -> tuple[dict[str, list[Row]], dict[str, list[Row]]]:
    """Build message-event indexes keyed by message and user in one pass.

    Args:
        dataframe: ``message_events`` dataframe.

    Returns:
        Tuple of ``(events_by_message, events_by_user)`` indexes.
    """
    _require_column(dataframe, MESSAGE_ID_COLUMN, "events_by_message")
    _require_column(dataframe, USER_ID_COLUMN, "events_by_user")

    events_by_message: dict[str, list[Row]] = defaultdict(list)
    events_by_user: dict[str, list[Row]] = defaultdict(list)

    for position in range(len(dataframe)):
        row = dataframe.iloc[position]
        events_by_message[_row_key(row, MESSAGE_ID_COLUMN)].append(row)
        events_by_user[_row_key(row, USER_ID_COLUMN)].append(row)

    by_message = dict(events_by_message)
    by_user = dict(events_by_user)
    _log_index_completed("events_by_message", len(by_message))
    _log_index_completed("events_by_user", len(by_user))
    return by_message, by_user


def _build_message_indexes(
    dataframe: pd.DataFrame,
) -> tuple[dict[str, list[Row]], dict[str, list[Row]], dict[str, list[Row]]]:
    """Build message indexes keyed by sender, group, and business in one pass.

    Args:
        dataframe: ``messages`` dataframe.

    Returns:
        Tuple of ``(messages_by_sender, messages_by_group, messages_by_business)``.
    """
    _require_column(dataframe, SENDER_ID_COLUMN, "messages_by_sender")
    _require_column(dataframe, GROUP_ID_COLUMN, "messages_by_group")
    _require_column(dataframe, BUSINESS_ID_COLUMN, "messages_by_business")

    by_sender: dict[str, list[Row]] = defaultdict(list)
    by_group: dict[str, list[Row]] = defaultdict(list)
    by_business: dict[str, list[Row]] = defaultdict(list)

    for position in range(len(dataframe)):
        row = dataframe.iloc[position]
        by_sender[_row_key(row, SENDER_ID_COLUMN)].append(row)
        by_group[_row_key(row, GROUP_ID_COLUMN)].append(row)
        by_business[_row_key(row, BUSINESS_ID_COLUMN)].append(row)

    sender_index = dict(by_sender)
    group_index = dict(by_group)
    business_index = dict(by_business)
    _log_index_completed("messages_by_sender", len(sender_index))
    _log_index_completed("messages_by_group", len(group_index))
    _log_index_completed("messages_by_business", len(business_index))
    return sender_index, group_index, business_index


def _log_index_completed(index_name: str, entry_count: int) -> None:
    """Log completion of a single index build step.

    Args:
        index_name: Name of the completed index.
        entry_count: Number of top-level keys in the index.
    """
    _logger.info("Built index %s (%d entries)", index_name, entry_count)


def _optional_value(row: Row, column: str) -> Any | None:
    """Return a row value as-is, or ``None`` when the cell is empty.

    Args:
        row: Source dataframe row.
        column: Column to read.

    Returns:
        Original cell value, or ``None`` if the cell is an empty string.
    """
    if column not in row.index:
        return None
    value = row[column]
    if value == "":
        return None
    return value


def _row_to_user(row: Row) -> User:
    """Map a user row to a User dataclass without inferring missing values.

    Args:
        row: Indexed user row.

    Returns:
        User instance populated from row values.
    """
    return User(
        user_id=str(row[USER_ID_COLUMN]),
        display_name=_optional_value(row, "display_name"),
        phone_number=_optional_value(row, "phone_number"),
    )


def _row_to_group(row: Row) -> Group:
    """Map a group row to a Group dataclass without inferring missing values.

    Args:
        row: Indexed group row.

    Returns:
        Group instance populated from row values.
    """
    member_count = _optional_value(row, "member_count")
    return Group(
        group_id=str(row[GROUP_ID_COLUMN]),
        name=_optional_value(row, "name"),
        member_count=int(member_count) if member_count is not None else None,
    )


def _row_to_business(row: Row) -> Business:
    """Map a business row to a Business dataclass without inferring missing values.

    Args:
        row: Indexed business row.

    Returns:
        Business instance populated from row values.
    """
    return Business(
        business_id=str(row[BUSINESS_ID_COLUMN]),
        name=_optional_value(row, "name"),
        category=_optional_value(row, "category"),
    )


def _row_to_message(row: Row) -> Message:
    """Map a Hackerrank messages.csv row to the internal Message model."""

    required_columns = (
        "message_id",
        "sender_user_id",
        "user_id",
        "conversation_type",
    )

    for column in required_columns:
        if column not in row.index:
            raise MissingIndexColumnError(
                f"Cannot map message row: column '{column}' missing"
            )

    # Media type
    media_value = (_optional_value(row, "media_type") or "").strip().lower()

    if media_value == "image":
        media_type = MediaType.IMAGE
    elif media_value == "voice":
        media_type = MediaType.VOICE
    else:
        media_type = MediaType.TEXT

    # Timestamp
    timestamp = pd.to_datetime(
        _optional_value(row, "created_at"),
        errors="coerce",
    )

    # Media reference
    media = None
    media_id = _optional_value(row, "media_id")

    if media_id is not None:
        media = MediaReference(
            media_id=str(media_id),
            media_type=media_type,
        )

    # Forwarded count
    forwarded = _optional_value(row, "forwarded_count")

    return Message(
        message_id=str(row["message_id"]),
        sender_id=str(row["sender_user_id"]),
        receiver_id=str(row["user_id"]),
        conversation_type=ConversationType(str(row["conversation_type"])),
        media_type=media_type,
        content=_optional_value(row, "message_text"),
        timestamp=None if pd.isna(timestamp) else timestamp,
        group_id=_optional_value(row, "group_id"),
        business_id=_optional_value(row, "business_id"),
        media=media,
        forwarded_count=int(forwarded or 0),
    )