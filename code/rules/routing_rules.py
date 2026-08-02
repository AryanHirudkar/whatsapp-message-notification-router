"""Deterministic routing rule function signatures."""

from code.data.models import MessageContext, Prediction


def apply_priority_rules(context: MessageContext) -> Prediction | None:
    """Apply high-priority deterministic routing rules.

    Args:
        context: Assembled message context.

    Returns:
        Prediction if a rule matches, otherwise ``None``.
    """
    # TODO: Implement priority rules.
    return None


def apply_mute_rules(context: MessageContext) -> Prediction | None:
    """Apply mute-specific routing rules.

    Args:
        context: Assembled message context.

    Returns:
        Prediction if a mute rule matches, otherwise ``None``.
    """
    # TODO: Implement mute rules.
    return None


def apply_digest_rules(context: MessageContext) -> Prediction | None:
    """Apply digest-specific routing rules.

    Args:
        context: Assembled message context.

    Returns:
        Prediction if a digest rule matches, otherwise ``None``.
    """
    # TODO: Implement digest rules.
    return None


def apply_notify_rules(context: MessageContext) -> Prediction | None:
    """Apply notify-specific routing rules.

    Args:
        context: Assembled message context.

    Returns:
        Prediction if a notify rule matches, otherwise ``None``.
    """
    # TODO: Implement notify rules.
    return None
