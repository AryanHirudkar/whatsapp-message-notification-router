"""Domain dataclasses for the WhatsApp notification router."""

from dataclasses import dataclass, field
from datetime import datetime

from code.schemas import Action, ConversationType, MediaType


@dataclass(frozen=True)
class User:
    """Represents a WhatsApp user."""

    user_id: str
    display_name: str | None = None
    phone_number: str | None = None


@dataclass(frozen=True)
class Business:
    """Represents a business account associated with messages."""

    business_id: str
    name: str | None = None
    category: str | None = None


@dataclass(frozen=True)
class Group:
    """Represents a WhatsApp group conversation."""

    group_id: str
    name: str | None = None
    member_count: int | None = None


@dataclass(frozen=True)
class MediaReference:
    """Reference to attached media for a message."""

    media_id: str
    media_type: MediaType

    file_path: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    duration_sec: float | None = None


@dataclass(frozen=True)
class Message:
    """Represents a single WhatsApp message."""

    message_id: str
    sender_id: str
    receiver_id: str
    conversation_type: ConversationType

    media_type: MediaType

    content: str | None = None
    timestamp: datetime | None = None

    group_id: str | None = None
    business_id: str |None = None

    media: MediaReference | None = None

    # NEW
    forwarded_count: int = 0


@dataclass(frozen=True)
class HistoricalMessage:
    """A prior message included in conversation history."""

    message: Message
    relative_order: int


@dataclass(frozen=True)
class MessageContext:
    """Aggregated context for routing a single message."""

    message: Message
    sender: User | None = None
    receiver: User | None = None
    group: Group | None = None
    business: Business | None = None
    history: tuple[HistoricalMessage, ...] = field(default_factory=tuple)
    interaction_history: tuple[HistoricalMessage, ...] = field(default_factory=tuple)
    notification_history: tuple[HistoricalMessage, ...] = field(default_factory=tuple)
    media_metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class Prediction:
    """Routing prediction for a message."""

    message_id: str
    action: Action
    message_type: ConversationType
    reason: str
    confidence: float
    evidence_message_ids: tuple[str, ...] = field(default_factory=tuple)
