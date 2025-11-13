"""LiteLLM-powered helpers with graceful fallbacks."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from rich.console import Console
from rich.panel import Panel
from denavy_common import JudgeDecision

from litellm import completion
from litellm.utils import Choices

DEFAULT_DECISION_PROMPT = """
You are a strict JSON-only Veto Engine.
Your *only* output must be a single, valid JSON object.
Do not add any text before or after the JSON.
Do not use markdown wrappers like ```json.
Review the user's discomfort and the proposed template steps.
Respond with JSON containing:
- "approved": boolean (true if the plan is good, false if it's irrelevant or bad)
- "reason": A short string explaining your decision.
""".strip()


class VetoEngine:
    """Thin wrapper around LiteLLM with JSON decoding fallbacks."""

    def __init__(self, model: str, system_prompt: Optional[str] = None, **kwargs: Any) -> None:
        self.model = model
        self.system_prompt = system_prompt or DEFAULT_DECISION_PROMPT
        self.kwargs = kwargs
        self.console = Console()

    def decide(self, user_prompt: str) -> Dict[str, Any]:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        json_kwargs = self.kwargs.copy()
        json_kwargs["response_format"] = {"type": "json_object"}

        try:
            response = completion(model=self.model, messages=messages, **json_kwargs)
            message = _extract_first_message(response.choices)
            return json.loads(message)
        
        except json.JSONDecodeError as exc:
            return {"approved": True, "reason": f"Judge failed JSON parsing ({exc}), defaulting to approve.", "raw": message}
        except Exception as exc:
            self.console.print(Panel.fit(f"Judge invocation failed: {exc}", title="Veto", style="red"))
            return JudgeDecision(approved=True, reason="Judge unavailable; fallback to approve").model_dump()


def _extract_first_message(choices: Choices) -> str:
    if not choices:
        return "{}"
    message = choices[0].get("message", {})
    return message.get("content", "{}")
