"""Collects user evaluation after presenting the proposed resolution."""

from __future__ import annotations

from typing import Dict

from rich.console import Console
from rich.panel import Panel

from denavy_common import BasePlugin, CycleState, PluginResult
from .registry import register_plugin


class CLIFeedbackPlugin(BasePlugin):
    name = "cli_feedback"
    description = "Shares the proposed resolution and captures subjective feedback."

    def __init__(self) -> None:
        self.console = Console()

    def run(self, state: CycleState, config: Dict[str, str]) -> PluginResult:
        resolution = state.get_value("proposed_resolution", "No resolution available.")
        self.console.print(Panel(resolution, title="Proposed Resolution", ))
        prompt = config.get("prompt", "How would you rate this proposal?")
        feedback = self.console.input(f"{prompt} ")
        state_updates = {"user_feedback": feedback}
        message = "Recorded feedback"
        return PluginResult(
            status="success",
            output={"feedback": feedback},
            state_updates=state_updates,
            tags=["feedback", "cli"],
            message=message,
        )


register_plugin(CLIFeedbackPlugin)
