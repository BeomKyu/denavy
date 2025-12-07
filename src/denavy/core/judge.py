"""The Veto Judge."""

from __future__ import annotations

from denavy.domain import CycleState, JudgeDecision, Template, PluginConfig
from denavy.llm import LLMService

JUDGE_PROMPT = """
You are the Veto Engine for Denavy.
Review the proposed plan against the user's request.

Output JSON:
{
  "approved": boolean,
  "reason": "string",
  "recommended_template": "string" or null
}

Criteria:
- Approve if the plan is logical and safe.
- Deny if it is harmful, irrelevant, or if a better template exists.
"""

class Judge:
    def evaluate(self, template: Template, state: CycleState) -> JudgeDecision:
        if not template.judge:
            return JudgeDecision(approved=True, reason="No judge configured.")

        llm = LLMService(model=template.judge.model, temperature=template.judge.temperature)

        # Build context
        plan_str = "\n".join([f"- {s.plugin}: {s.config}" for s in template.steps])
        user_input = state.user_input or "(No user input)"

        prompt = f"""
User Input: {user_input}

Proposed Plan:
{plan_str}

Evaluate this plan.
"""

        result = llm.call(
            system_prompt=template.judge.system_prompt or JUDGE_PROMPT,
            user_prompt=prompt,
            json_mode=True
        )

        return JudgeDecision(**result)
