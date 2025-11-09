"""LLM-backed resolver with graceful degradation when API keys are absent."""

from __future__ import annotations

from typing import Any, Dict

from litellm import completion
from rich.console import Console

from denavy_common import BasePlugin, CycleState, PluginExecutionError, PluginResult
from .registry import register_plugin


class SimpleLLMResolverPlugin(BasePlugin):
    name = "simple_llm_resolver"
    description = "Synthesises a resolution proposal using an LLM or fallback heuristics."

    def __init__(self) -> None:
        self.console = Console()

    def run(self, state: CycleState, config: Dict[str, Any]) -> PluginResult:
        discomfort = state.get_value("user_input", "")
        if not discomfort:
            raise PluginExecutionError("No user_input present in state; run cli_input first")

        prompt_template = config.get(
            "prompt_template",
            "You are an assistant helping with the following discomfort: {discomfort}. Provide a concise actionable plan.",
        )
        
        # Gather all state values that might be used in the template
        template_vars = {
            "discomfort": discomfort,
            "file_contents": state.get_value("file_contents", ""),
        }
        
        user_prompt = prompt_template.format(**template_vars)
        model = config.get("model", "gpt-4o-mini")
        system_prompt = config.get(
            "system_prompt",
            "You are Denavy's resolver plugin. Respond with a concise plan in numbered steps.",
        )

        try:
            response = completion(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=config.get("temperature", 0.3),
                max_tokens=config.get("max_tokens", 4096),
            )
            content = response.choices[0]["message"]["content"]
            message = f"Generated plan with {model}"
        except Exception as exc:  # noqa: BLE001
            content = self._fallback(discomfort)
            message = f"Fallback resolution: {exc}"

        state_updates = {"proposed_resolution": content}
        return PluginResult(
            status="success",
            output={"resolution": content},
            state_updates=state_updates,
            tags=["llm", "resolution"],
            message=message,
        )

    def _fallback(self, discomfort: str) -> str:
        baseline = [
            f"Clarify the discomfort: '{discomfort}'",
            "List the constraints and desired outcomes",
            "Draft a minimum viable test to validate improvements",
            "Schedule a feedback check in 24 hours",
        ]
        return "\n".join(f"{idx + 1}. {step}" for idx, step in enumerate(baseline))


register_plugin(SimpleLLMResolverPlugin)
