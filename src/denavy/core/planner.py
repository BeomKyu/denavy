"""The AI Planner."""

from __future__ import annotations

from typing import List

from denavy.domain import CycleState, PluginConfig
from denavy.llm import LLMService

PLANNER_PROMPT = """
You are the Denavy Planner.
Generate a list of execution steps (plugins) to address the user's request or fix a failure.

Available Plugins:
- executor (command, code, filename)
- git_committer (message, push)
- cli_input (prompt)
- simple_llm (system_prompt, user_prompt)

Output JSON:
{
  "steps": [
    { "plugin": "name", "config": { ... } }
  ],
  "reason": "explanation"
}
"""

class Planner:
    def __init__(self, model: str = "gpt-4-turbo"):
        self.llm = LLMService(model=model)

    def generate_plan(self, state: CycleState, context: str) -> List[PluginConfig]:
        prompt = f"""
Cycle ID: {state.cycle_id}
User Input: {state.user_input}
Context/Error: {context}

Generate a repair plan.
"""
        result = self.llm.call(PLANNER_PROMPT, prompt, json_mode=True)

        steps = []
        for s in result.get("steps", []):
            try:
                steps.append(PluginConfig(**s))
            except Exception:
                continue
        return steps
