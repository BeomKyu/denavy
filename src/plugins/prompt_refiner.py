"""Plugin that refines vague user input into specific technical instructions."""

from __future__ import annotations

from typing import Any, Dict

from litellm import completion
from rich.console import Console
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text

from denavy_common import BasePlugin, CycleState, PluginExecutionError, PluginResult
from .registry import register_plugin


class PromptRefinerPlugin(BasePlugin):
    name = "prompt_refiner"
    description = "Refines vague user input into specific technical instructions using context."

    def __init__(self) -> None:
        self.console = Console()

    def run(self, state: CycleState, config: Dict[str, Any]) -> PluginResult:
        user_input = state.user_input
        if not user_input:
            # If no input, we can't refine anything.
            # Depending on design, we might skip or error. 
            # Given the flow, it's likely an error if this runs without input.
            raise PluginExecutionError("No user_input present in state; cannot refine prompt.")

        file_contents = state.file_contents or "(No file context provided)"

        # 1. Construct the prompt for the LLM
        prompt_template = config.get(
            "prompt_template",
            "You are a technical lead. Refine the following vague user request into a specific, actionable technical instruction based on the provided code context.\n\nUser Request: {user_input}\n\nCode Context:\n{file_contents}\n\nRefined Instruction:",
        )
        
        # Truncate file_contents if too large to avoid token limits (basic safety)
        # In a real scenario, we might want smarter context selection.
        max_context_len = config.get("max_context_len", 10000)
        if len(file_contents) > max_context_len:
            file_contents = file_contents[:max_context_len] + "...(truncated)"

        user_prompt = prompt_template.format(user_input=user_input, file_contents=file_contents)
        
        model = config.get("model", "gpt-4o-mini")
        system_prompt = config.get(
            "system_prompt",
            "You are an expert software architect. Output ONLY the refined technical instruction. Do not add preamble.",
        )

        try:
            response = completion(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=config.get("temperature", 0.1),
            )
            refined_instruction = response.choices[0]["message"]["content"].strip()
            
        except Exception as exc:
            # If LLM fails, we log it and keep the original input, or fail?
            # Let's fail gracefully by keeping original but noting the error.
            self.console.print(f"[yellow]Warning: Prompt refinement failed ({exc}). Using original input.[/yellow]")
            refined_instruction = user_input
            
        # 2. Update state with refined input
        # We update the user_input in the state so subsequent plugins see the refined version.
        # We also store the original for record-keeping if needed, maybe in scratchpad.
        original_input = user_input
        state.user_input = refined_instruction
        state.set_scratchpad("original_user_input", original_input)

        # 3. UX: Display "Original vs Refined" comparison
        self._display_comparison(original_input, refined_instruction)

        return PluginResult(
            status="success",
            output={"original_input": original_input, "refined_input": refined_instruction},
            user_input=refined_instruction, # Explicitly return updated input
            tags=["prompt_refinement"],
            message="Refined user input",
        )

    def _display_comparison(self, original: str, refined: str) -> None:
        """Displays a side-by-side comparison of the original and refined prompts."""
        original_panel = Panel(Text(original, style="red"), title="Original Input", title_align="left")
        refined_panel = Panel(Text(refined, style="green"), title="Refined Input", title_align="left")
        
        self.console.print(Columns([original_panel, refined_panel]))


register_plugin(PromptRefinerPlugin)
