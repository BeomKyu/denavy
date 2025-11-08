"""Built-in reference plugins bundled with Denavy."""

# Import side effects register plugins with the registry
from . import cli_feedback, cli_input, simple_llm_resolver, summarizer, context_aware_reolver  # noqa: F401

__all__ = [
    "cli_feedback",
    "cli_input",
    "simple_llm_resolver",
    "summarizer",
    "context_aware_reolver",
]
