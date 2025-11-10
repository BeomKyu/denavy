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
        
        self.console.print(f"{prompt}")
        self.console.print("--- (입력을 시작하세요. 완료하려면 [Ctrl+D] 또는 [Ctrl+Z] 후 [Enter]) ---")
        
        lines = []
        try:
            while True:
                line = input()
                lines.append(line)
        except EOFError:
            pass  # 입력이 끝났음을 의미

        response = "\n".join(lines)
        
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
