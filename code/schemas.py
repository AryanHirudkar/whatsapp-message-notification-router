"""Single source of truth for domain constants and output schema."""

from enum import StrEnum

from typing import Final


class Action(StrEnum):
    """Routing actions for message notifications."""

    NOTIFY = "notify"
    DIGEST = "digest"
    MUTE = "mute"


class ConversationType(StrEnum):
    """Types of WhatsApp conversations."""

    PERSONAL = "personal"
    GROUP = "group"
    BUSINESS = "business"


class MediaType(StrEnum):
    """Supported message media types."""

    TEXT = "text"
    IMAGE = "image"
    VOICE = "voice"
    

class MessageType(StrEnum):
    """Message classification categories."""

    PERSONAL = "personal"
    URGENT = "urgent"
    EVENT = "event"
    PAYMENT = "payment"
    BUSINESS_UPDATE = "business_update"
    PROMOTION = "promotion"
    GREETING = "greeting"
    FORWARD = "forward"
    SPAM = "spam"
    SCAM = "scam"
    UNKNOWN = "unknown"

OUTPUT_COLUMNS: Final[tuple[str, ...]] = (
    "message_id",
    "action",
    "message_type",
    "reason",
    "confidence",
    "evidence_message_ids",
)
