"""Captures multi-line user input from the CLI."""

from __future__ import annotations
from typing import Any, Dict

from prompt_toolkit import prompt
# '진화': Output 임포트 제거
# from prompt_toolkit.output import Output 

from denavy_common import BasePlugin, CycleState, PluginResult
from .registry import register_plugin


# '진화': 'output' 인자 시그니처에서 제거
def _read_multi_line_input(prompt_text: str) -> str:
    """
    Read multi-line input using prompt_toolkit (multiline=True mode).
    - Enter inserts a newline.
    - Alt+Enter or Esc+Enter submits the input.
    """
    print(prompt_text)
    print("--- (입력을 시작하세요. [Enter]로 줄바꿈, [Alt+Enter]로 전송) ---")
    
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


class CliInputPlugin(BasePlugin):
    name = "cli_input"
    description = "Captures multi-line input from the user CLI."

    def run(self, state: CycleState, config: Dict[str, Any]) -> PluginResult:
        prompt_text = config.get("prompt", "Input:")
        
        # '진화': output_stream 관련 로직 모두 제거
        
        try:
            # '진화': 'output' 인자 없이 호출
            user_input = _read_multi_line_input(prompt_text)
            
            if not user_input:
                return PluginResult(status="error", message="Input aborted.")
                
        except Exception as e:
            return PluginResult(status="error", message=f"Input failed: {e}")
        
        return PluginResult(
            status="success",
            output={"user_input": user_input},
            user_input=user_input,
            message="Captured CLI input",
        )

register_plugin(CliInputPlugin)
