"""Built-in reference plugins bundled with Denavy."""

# Import side effects register plugins with the registry
from . import cli_feedback, cli_input, context_aware_resolver, simple_llm_resolver, summarizer  # noqa: F401

__all__ = [
    "cli_feedback",
    "cli_input",
    "context_aware_resolver",
    "simple_llm_resolver",
    "summarizer",
]
