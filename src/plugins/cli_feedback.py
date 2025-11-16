"""Collects user evaluation after presenting the proposed resolution."""

from __future__ import annotations

from typing import Dict

from prompt_toolkit import prompt
# '진화': Output 임포트 제거
# from prompt_toolkit.output import Output 

from rich.console import Console
from rich.panel import Panel

from denavy_common import BasePlugin, CycleState, PluginResult
from .registry import register_plugin


# '진화': 'output' 인자 시그니처에서 제거
def _read_multi_line_feedback(prompt_text: str) -> str:
    """
    Read multi-line input using prompt_toolkit (multiline=True mode).
    - Enter inserts a newline.
    - Alt+Enter or Esc+Enter submits the input.
    """
    print(prompt_text)
    print("--- (피드백을 입력하세요. [Enter]로 줄바꿈, [Alt+Enter]로 전송) ---")
    
    try:
        user_input = prompt(
            "> ", 
            multiline=True,
            # '진화': output=output 인자 제거
        )
        return user_input
    except EOFError:
        print("^Z")
        return ""
    except Exception as e:
        print(f"[WARN] prompt_toolkit failed, falling back to basic input. Error: {e}")
        try:
            return input("> ")
        except EOFError:
            print("^Z")
            return ""


class CLIFeedbackPlugin(BasePlugin):
    name = "cli_feedback"
    description = "Shares the proposed resolution and captures subjective feedback."

    def __init__(self) -> None:
        self.console = Console()

    def run(self, state: CycleState, config: Dict[str, str]) -> PluginResult:
        
        resolution = state.proposed_resolution or "No resolution available."
        
        self.console.print(Panel(resolution, title="Proposed Resolution", ))
        
        prompt_text = config.get("prompt", "How would you rate this proposal?")
        
        # '진화': output_stream 관련 로직 모두 제거

        try:
            # '진화': 'output' 인자 없이 호출
            feedback = _read_multi_line_feedback(prompt_text)
            
        except Exception as e:
            return PluginResult(status="error", message=f"Feedback input failed: {e}")

        message = "Recorded feedback"
        return PluginResult(
            status="success",
            output={"user_feedback": feedback},
            user_feedback=feedback,
            tags=["feedback", "cli"],
            message=message,
        )

register_plugin(CLIFeedbackPlugin)
