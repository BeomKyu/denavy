"""The AI Planner component for dynamic plan generation and self-repair."""

from __future__ import annotations

from typing import List, Optional, Any

from denavy_common import (
    CycleState,
    PluginConfig,
)
from plugins.registry import list_plugins

from .llm import VetoEngine


PLANNER_SYSTEM_PROMPT = """
You are the Planner for Denavy, an AI orchestration engine.
Your goal is to generate a list of execution steps (plugins) to address a user's request or fix a failure.

Available Plugins:
{plugin_list}

Input:
You will receive the current cycle state, including user input and any recent errors.

Output Format:
You must output a SINGLE valid JSON object.
Do NOT add any markdown formatting.

JSON Structure:
{{
  "steps": [
    {{
      "plugin": "string", // Name of the plugin to execute (must be one of the available plugins)
      "config": {{ ... }}   // Configuration dictionary for the plugin
    }}
  ],
  "reason": "string" // Explanation for the plan
}}

Instructions:
- If the user is reporting a problem, select plugins that can diagnose or fix it.
- If a previous step failed, analyze the error and select plugins to fix the issue and retry.
- You can chain multiple plugins.
""".strip()


class Planner:
    """Generates execution plans using an LLM."""

    def __init__(self, model: str = "gpt-4-turbo") -> None:
        # Default to a capable model for planning, can be configured
        self.model = model

    def generate_plan(
        self,
        state: CycleState,
        context_msg: str = "",
        model_override: Optional[str] = None
    ) -> List[PluginConfig]:
        """
        Generate a list of steps to execute based on the current state and context.

        Args:
            state: The current cycle state.
            context_msg: Additional context, e.g., "Step X failed with error Y".
            model_override: Optional model to use instead of the default.
        """

        plugin_list = "\n".join(f"- {name}" for name in list_plugins())
        system_prompt = PLANNER_SYSTEM_PROMPT.format(plugin_list=plugin_list)

        user_prompt = f"""
Cycle ID: {state.cycle_id}
User Input: {state.user_input or 'None'}
Proposed Resolution (so far): {state.proposed_resolution or 'None'}
Context/Issue: {context_msg}

Please generate a plan to proceed.
"""

        engine = VetoEngine(
            model=model_override or self.model,
            system_prompt=system_prompt,
            temperature=0.7 # Allow some creativity/exploration in planning
        )

        response = engine.decide(user_prompt)

        steps_data = response.get("steps", [])
        plan = []
        for step_data in steps_data:
            try:
                plan.append(PluginConfig(
                    plugin=step_data["plugin"],
                    config=step_data.get("config", {})
                ))
            except Exception:
                # Skip invalid steps
                continue

        return plan
