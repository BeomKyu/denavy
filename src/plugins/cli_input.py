"""Captures multi-line user input from the CLI."""

from __future__ import annotations
from typing import Any, Dict

from denavy_common import BasePlugin, CycleState, PluginResult
from .registry import register_plugin


def _read_multi_line_input(prompt: str) -> str:
    """Read multi-line input, ending with Ctrl+D or Ctrl+Z."""
    print(prompt)
    print("--- (입력을 시작하세요. 완료하려면 [Ctrl+D] 또는 [Ctrl+Z] 후 [Enter]) ---")
    lines = []
    while True:
        try:
            line = input()
            lines.append(line)
        except EOFError:
            print("^Z")
            break
    return "\n".join(lines)


class CliInputPlugin(BasePlugin):
    name = "cli_input"
    description = "Captures multi-line input from the user CLI."

    def run(self, state: CycleState, config: Dict[str, Any]) -> PluginResult:
        prompt_text = config.get("prompt", "Input:")
        
        try:
            user_input = _read_multi_line_input(prompt_text)
        except EOFError:
            return PluginResult(status="error", message="Input aborted.")
        
        return PluginResult(
            status="success",
            output={"user_input": user_input},
            
            user_input=user_input,
            
            message="Captured CLI input",
        )

register_plugin(CliInputPlugin)
