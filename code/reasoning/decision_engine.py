"""Routing decision engine interface."""

from abc import ABC, abstractmethod

from code.data.models import MessageContext, Prediction


class DecisionEngine(ABC):
    """Abstract interface for message routing decisions.

    No implementation.
    """

    @abstractmethod
    def decide(self, context: MessageContext) -> Prediction:
        """Produce a routing prediction for a message context.

        Args:
            context: Assembled message context.

        Returns:
            Routing prediction.
        """
        # TODO: Implement in concrete decision engine.

    @abstractmethod
    def decide_batch(self, contexts: list[MessageContext]) -> list[Prediction]:
        """Produce routing predictions for a batch of contexts.

        Args:
            contexts: List of assembled message contexts.

        Returns:
            Routing predictions in the same order as input contexts.
        """
        # TODO: Implement in concrete decision engine.
