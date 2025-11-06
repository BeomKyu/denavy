"""LiteLLM-powered helpers with graceful fallbacks."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from litellm import completion
from litellm.utils import Choices

DEFAULT_DECISION_PROMPT = """
You are the Denavy template judge. Review the proposed execution template and decide
whether it should run as-is. Respond with a JSON object containing:
- approved: boolean
- reason: short sentence explaining your choice
""".strip()


class VetoEngine:
    """Thin wrapper around LiteLLM with JSON decoding fallbacks."""

    def __init__(self, model: str, system_prompt: Optional[str] = None, **kwargs: Any) -> None:
        self.model = model
        self.system_prompt = system_prompt or DEFAULT_DECISION_PROMPT
        self.kwargs = kwargs

    def decide(self, user_prompt: str) -> Dict[str, Any]:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        response = completion(model=self.model, messages=messages, **self.kwargs)
        message = _extract_first_message(response.choices)
        try:
            return json.loads(message)
        except json.JSONDecodeError:
            return {"approved": True, "reason": "Non-JSON response from judge, defaulting to approve.", "raw": message}


def _extract_first_message(choices: Choices) -> str:
    if not choices:
        return "{}"
    message = choices[0].get("message", {})
    return message.get("content", "{}")
