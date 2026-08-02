"""LLM provider interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMResponse:
    """Structured response from an LLM provider."""

    content: str
    model: str | None = None
    tokens_used: int | None = None


class LLMClient(ABC):
    """Abstract interface for large language model providers.

    No prompt construction logic.
    """

    @abstractmethod
    def complete(self, prompt: str) -> LLMResponse:
        """Send a completion request to the LLM.

        Args:
            prompt: Fully constructed prompt string.

        Returns:
            LLM response content.
        """
        # TODO: Implement in concrete provider.

    @abstractmethod
    def complete_with_retry(self, prompt: str, max_retries: int) -> LLMResponse:
        """Send a completion request with retry semantics.

        Args:
            prompt: Fully constructed prompt string.
            max_retries: Maximum number of retry attempts.

        Returns:
            LLM response content.

        Raises:
            RuntimeError: If all retry attempts fail.
        """
        # TODO: Implement in concrete provider.
