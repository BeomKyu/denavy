"""Custom exception hierarchy for Denavy."""


class DenavyError(Exception):
    """Base exception for Denavy-specific failures."""


class TemplateLoadError(DenavyError):
    """Raised when a template cannot be parsed or validated."""


class PluginExecutionError(DenavyError):
    """Raised when a plugin fails during execution."""
