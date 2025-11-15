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
        
        resolution = state.proposed_resolution or "No resolution available."
        
        self.console.print(Panel(resolution, title="Proposed Resolution", ))
        
        prompt = config.get("prompt", "How would you rate this proposal?")
        
        self.console.print(f"{prompt}")
        self.console.print("--- (피드백을 입력하세요. 완료하려면 [Ctrl+D] 또는 [Ctrl+Z] 후 [Enter]) ---")
        
        lines = []
        try:
            while True:
                line = input()
                lines.append(line)
        except EOFError:
            print("^Z")
            pass

        feedback = "\n".join(lines)
        
        message = "Recorded feedback"
        return PluginResult(
            status="success",
            output={"user_feedback": feedback},
            
            user_feedback=feedback,
            
            tags=["feedback", "cli"],
            message=message,
        )


register_plugin(CLIFeedbackPlugin)
