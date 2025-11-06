"""Common contracts and shared types for Denavy."""

from .contracts import (
    BasePlugin,
    CycleState,
    EventLogEntry,
    IndexRecord,
    JudgeDecision,
    PluginConfig,
    PluginResult,
    SummaryDocument,
)
from .exceptions import DenavyError, PluginExecutionError, TemplateLoadError

__all__ = [
    "BasePlugin",
    "CycleState",
    "DenavyError",
    "EventLogEntry",
    "IndexRecord",
    "JudgeDecision",
    "PluginConfig",
    "PluginExecutionError",
    "PluginResult",
    "SummaryDocument",
    "TemplateLoadError",
]
