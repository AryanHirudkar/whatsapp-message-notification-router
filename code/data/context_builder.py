"""Message context assembly for routing."""

from datetime import datetime
from typing import Any, Final

import pandas as pd

from code.config import Config
from code.data.indexer import (
    BUSINESS_ID_COLUMN,
    GROUP_ID_COLUMN,
    MESSAGE_ID_COLUMN,
    USER_ID_COLUMN,
    MessageIndexer,
    Row,
)
from code.data.models import HistoricalMessage, MediaReference, Message, MessageContext
from code.schemas import ConversationType, MediaType
from code.utils.logger import get_logger

_logger = get_logger("data.context_builder")

SENDER_USER_ID_COLUMN: Final[str] = "sender_user_id"
MESSAGE_TEXT_COLUMN: Final[str] = "message_text"
MEDIA_TYPE_COLUMN: Final[str] = "media_type"
MEDIA_ID_COLUMN: Final[str] = "media_id"
CREATED_AT_COLUMN: Final[str] = "created_at"
FILE_PATH_COLUMN: Final[str] = "file_path"
NOTIFICATION_DISMISSED_COLUMN: Final[str] = "notification_dismissed"
MUTED_AFTER_MESSAGE_COLUMN: Final[str] = "muted_after_message"
MESSAGE_OPENED_COLUMN: Final[str] = "message_opened"


class ContextBuilder:
    """Creates MessageContext objects by gathering related data.

    No routing decisions.
    """

    def __init__(self, indexer: MessageIndexer, config: Config) -> None:
        """Initialize the context builder.

        Args:
            indexer: Populated message indexer.
            config: Application configuration.
        """
        self._indexer = indexer
        self._config = config
        self._history_by_message_id: dict[str, Row] | None = None

    def build(self, message: Message) -> MessageContext:
        """Assemble full context for a message.

        Gathers message, receiver, sender, group, business, history,
        interaction history, notification history, and media metadata.

        Args:
            message: Target message to build context for.

        Returns:
            Populated MessageContext instance.
        """
        store = self._indexer.store
        receiver_id = message.receiver_id

        history = self._build_history(message, store.history_by_user.get(receiver_id, []))
        user_events = store.events_by_user.get(receiver_id, [])
        interaction_history = self._build_interaction_history(user_events)
        notification_history = self._build_notification_history(user_events)
        notification_summary = self._build_notification_summary(
            store.notifications_by_user.get(receiver_id, []),
        )
        media_metadata = self._build_media_metadata(message, notification_summary)

        context = MessageContext(
            message=message,
            sender=self._indexer.get_user(message.sender_id),
            receiver=self._indexer.get_user(receiver_id),
            group=(
                self._indexer.get_group(message.group_id)
                if message.group_id
                else None
            ),
            business=(
                self._indexer.get_business(message.business_id)
                if message.business_id
                else None
            ),
            history=history,
            interaction_history=interaction_history,
            notification_history=notification_history,
            media_metadata=media_metadata,
        )
        _logger.debug(
            "Built context for message %s (history=%d, interactions=%d, notifications=%d)",
            message.message_id,
            len(history),
            len(interaction_history),
            len(notification_history),
        )
        return context

    def _build_history(self, message: Message, rows: list[Row]) -> tuple[HistoricalMessage, ...]:
        """Build conversation history for the receiving user.

        Args:
            message: Incoming message being routed.
            rows: Historical message rows in original CSV order.

        Returns:
            Up to ``max_history_messages`` most recent historical messages.
        """
        history_rows = self._get_relevant_history(message, rows)

        return self._rows_to_historical_messages(history_rows)

    def _get_relevant_history(self, message: Message, rows: list[Row], ) -> list[Row]:
        """Return the most relevant historical rows for the incoming message."""

        scored_rows: list[tuple[int, Row]] = []

        for row in rows:
            score = 0

             # Same sender
            if _optional_value(row, SENDER_USER_ID_COLUMN) == message.sender_id:
                score += 100

            # Same business
            if (
                message.business_id
                and _optional_value(row, BUSINESS_ID_COLUMN) == message.business_id
            ):
                score += 80

            # Same group
            if (
                message.group_id
                and _optional_value(row, GROUP_ID_COLUMN) == message.group_id
            ):
                score += 70

            # Same conversation type
            if (
                _optional_value(row, "conversation_type")
                == message.conversation_type.value
            ):
                score += 40

            # Same media type
            if (
                _optional_value(row, MEDIA_TYPE_COLUMN)
                == message.media_type.value
            ):
                score += 20

        scored_rows.append((score, row))

        scored_rows.sort(key=lambda item: item[0], reverse=True)

        return [
            row
            for _, row in scored_rows[: self._config.max_history_messages]
         ]
    
    def _build_interaction_history(
        self,
        event_rows: list[Row],
    ) -> tuple[HistoricalMessage, ...]:
        """Build interaction history from user message-event rows.

        Args:
            event_rows: Message-event rows for the receiving user.

        Returns:
            Historical messages referenced by the user's recent events.
        """
        history_rows = self._resolve_event_history_rows(
            _take_last_rows(event_rows, self._config
                            .max_history_messages),
        )
        return self._rows_to_historical_messages(history_rows)

    def _build_notification_history(
        self,
        event_rows: list[Row],
    ) -> tuple[HistoricalMessage, ...]:
        """Build notification-related history from user message-event rows.

        Args:
            event_rows: Message-event rows for the receiving user.

        Returns:
            Historical messages tied to recent notification interactions.
        """
        notification_events = [
            row for row in event_rows if _is_notification_event(row)
        ]
        history_rows = self._resolve_event_history_rows(
            _take_last_rows(
                notification_events,
                self._config.max_history_messages,
            ),
        )
        return self._rows_to_historical_messages(history_rows)

    def _build_notification_summary(
        self,
        notification_rows: list[Row],
    ) -> tuple[dict[str, object], ...]:
        """Build daily notification summary slices for the receiving user.

        Args:
            notification_rows: Notification summary rows for the user.

        Returns:
            Recent notification summary rows preserved as dictionaries.
        """
        return tuple(
            _row_to_dict(row)
            for row in _take_last_rows(
                notification_rows,
                self._config.max_history_messages,
            )
        )

    def _build_media_metadata(
        self,
        message: Message,
        notification_summary: tuple[dict[str, object], ...],
    ) -> dict[str, object]:
        """Attach media and auxiliary metadata for the target message.

        Args:
            message: Target incoming message.
            notification_summary: Recent daily notification summary rows.

        Returns:
            Metadata dictionary with preserved row values only.
        """
        metadata: dict[str, object] = {}

        if notification_summary:
            metadata["notification_summary"] = notification_summary

        if not self._config.enable_media:
            return metadata

        if message.media is not None:
            metadata["media"] = {
                "media_type": message.media.media_type.value,
                "file_path": message.media.file_path,
                "mime_type": message.media.mime_type,
                "size_bytes": message.media.size_bytes,
                "duration_sec": message.media.duration_sec,
            }

        image_row = self._lookup_image_row(message)
        if image_row is not None:
            metadata["image"] = _row_to_dict(image_row)

        return metadata

    def _lookup_image_row(self, message: Message) -> Row | None:
        """Resolve an indexed image row for an image message when possible.

        Args:
            message: Target incoming message.

        Returns:
            Matching image row, or ``None`` when no indexed match exists.
        """
        if message.media_type != MediaType.IMAGE:
            return None

        if message.media is not None and message.media.file_path:
            for row in self._indexer.store.images_by_id.values():
                if _optional_value(row, FILE_PATH_COLUMN) == message.media.file_path:
                    return row

        return None

    def _resolve_event_history_rows(self, event_rows: list[Row]) -> list[Row]:
        """Map message-event rows to their historical message rows.

        Args:
            event_rows: Message-event rows in CSV order.

        Returns:
            Historical message rows referenced by the events, preserving order.
        """
        history_index = self._get_history_by_message_id()
        resolved: list[Row] = []
        for event_row in event_rows:
            message_id = _optional_value(event_row, MESSAGE_ID_COLUMN)
            if message_id is None:
                continue
            history_row = history_index.get(str(message_id))
            if history_row is not None:
                resolved.append(history_row)
        return resolved

    def _rows_to_historical_messages(
        self,
        rows: list[Row],
    ) -> tuple[HistoricalMessage, ...]:
        """Convert historical message rows to ordered HistoricalMessage tuples.

        Args:
            rows: Historical message rows in CSV order.

        Returns:
            Historical messages with zero-based relative order within the slice.
        """
        historical_messages: list[HistoricalMessage] = []
        for relative_order, row in enumerate(rows):
            historical_message = _history_row_to_message(row)
            if historical_message is None:
                continue
            historical_messages.append(
                HistoricalMessage(
                    message=historical_message,
                    relative_order=relative_order,
                )
            )
        return tuple(historical_messages)

    def _get_history_by_message_id(self) -> dict[str, Row]:
        """Return a lazily built message-id index over all historical messages.

        Returns:
            Mapping of historical ``message_id`` to source row.
        """
        if self._history_by_message_id is None:
            index: dict[str, Row] = {}
            for rows in self._indexer.store.history_by_user.values():
                for row in rows:
                    message_id = _optional_value(row, MESSAGE_ID_COLUMN)
                    if message_id is not None:
                        index[str(message_id)] = row
            self._history_by_message_id = index
        return self._history_by_message_id


def _take_last_rows(rows: list[Row], limit: int) -> list[Row]:
    """Return the last ``limit`` rows, preserving order.

    Args:
        rows: Source rows in CSV order.
        limit: Maximum number of rows to keep.

    Returns:
        Tail slice of the input rows.
    """
    if limit <= 0 or not rows:
        return []
    return rows[-limit:]


def _optional_value(row: Row, column: str) -> Any | None:
    """Return a row value as-is, or ``None`` when the cell is empty.

    Args:
        row: Source dataframe row.
        column: Column to read.

    Returns:
        Original cell value, or ``None`` if the cell is absent or empty.
    """
    if column not in row.index:
        return None
    value = row[column]
    if value == "":
        return None
    return value


def _row_to_dict(row: Row) -> dict[str, object]:
    """Convert a dataframe row to a dictionary without modifying values.

    Args:
        row: Source dataframe row.

    Returns:
        Dictionary keyed by original column names.
    """
    return {str(column): row[column] for column in row.index}


def _parse_media_type(raw_value: Any | None) -> MediaType | None:
    """Map a CSV media-type cell to a MediaType enum value.

    Args:
        raw_value: Raw media-type cell value.

    Returns:
        Matching MediaType, or ``None`` when the cell is empty.
    """
    if raw_value is None or raw_value == "":
        return MediaType.TEXT
    return MediaType(str(raw_value))


def _parse_timestamp(raw_value: Any | None) -> datetime | None:
    """Parse a timestamp cell when present.

    Args:
        raw_value: Raw timestamp cell value.

    Returns:
        Parsed datetime, or ``None`` when the cell is empty.
    """
    if raw_value is None or raw_value == "":
        return None
    return datetime.fromisoformat(str(raw_value))


def _history_row_to_message(row: Row) -> Message | None:
    """Map a message-history row to a Message dataclass."""

    message_id = _optional_value(row, MESSAGE_ID_COLUMN)
    receiver_id = _optional_value(row, USER_ID_COLUMN)
    conversation_type = _optional_value(row, "conversation_type")
    media_type = _parse_media_type(_optional_value(row, MEDIA_TYPE_COLUMN))

    if message_id is None or receiver_id is None or conversation_type is None:
        return None

    if media_type is None:
        return None

    # Build media reference
    media_reference = None
    media_id = _optional_value(row, MEDIA_ID_COLUMN)

    if media_id is not None and media_type in (
        MediaType.IMAGE,
        MediaType.VOICE,
    ):
        media_reference = MediaReference(
            media_id=str(media_id),
            media_type=media_type,
        )

    sender_id = (
        str(row[SENDER_USER_ID_COLUMN])
        if SENDER_USER_ID_COLUMN in row.index
        else ""
    )

    forwarded = _optional_value(row, "forwarded_count")

    return Message(
        message_id=str(message_id),
        sender_id=sender_id,
        receiver_id=str(receiver_id),
        conversation_type=ConversationType(str(conversation_type)),
        media_type=media_type,
        content=_optional_value(row, MESSAGE_TEXT_COLUMN),
        timestamp=_parse_timestamp(_optional_value(row, CREATED_AT_COLUMN)),
        group_id=_optional_value(row, GROUP_ID_COLUMN),
        business_id=_optional_value(row, BUSINESS_ID_COLUMN),
        media=media_reference,
        forwarded_count=int(forwarded or 0),
    )


def _is_notification_event(row: Row) -> bool:
    """Return whether a message-event row records notification interaction.

    Args:
        row: Message-event row from ``message_events.csv``.

    Returns:
        ``True`` when the row records open, dismiss, or mute-after-notification.
    """
    for column in (
        MESSAGE_OPENED_COLUMN,
        NOTIFICATION_DISMISSED_COLUMN,
        MUTED_AFTER_MESSAGE_COLUMN,
    ):
        value = _optional_value(row, column)
        if value in (1, "1"):
            return True
    return False
