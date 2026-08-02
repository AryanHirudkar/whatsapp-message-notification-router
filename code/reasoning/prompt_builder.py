"""Prompt construction for LLM-based routing."""

from code.data.models import MessageContext


class PromptBuilder:
    """Builds prompts for the decision engine.

    Empty prompt builder class. No prompt templates yet.
    """

    def build_routing_prompt(self, context: MessageContext) -> str:
        """Build a routing prompt from message context.

        Args:
            context: Assembled message context.

        Returns:
            Prompt string for the LLM.
        """
        # TODO: Implement prompt template construction.
        raise NotImplementedError("Prompt building not yet implemented")

    def build_system_prompt(self) -> str:
        """Build the system-level instruction prompt.

        Returns:
            System prompt string.
        """
        # TODO: Implement system prompt template.
        raise NotImplementedError("System prompt not yet implemented")
