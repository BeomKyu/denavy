"""CLI plugin to capture the user's discomfort statement."""

from __future__ import annotations

from rich.console import Console

from denavy_common import BasePlugin, CycleState, PluginResult
from .registry import register_plugin


class CLIInputPlugin(BasePlugin):
    name = "cli_input"
    description = "Collects the cycle's starting discomfort via the terminal."

    def __init__(self) -> None:
        self.console = Console()

    def run(self, state: CycleState, config: dict) -> PluginResult:
        prompt = config.get("prompt", "Describe the discomfort to address")
        response = self.console.input(f"{prompt}: ")
        state_updates = {"user_input": response}
        message = "Captured CLI input"
        return PluginResult(
            status="success",
            output={"user_input": response},
            state_updates=state_updates,
            tags=["cli", "input"],
            message=message,
        )


register_plugin(CLIInputPlugin)
