"""LLM interaction layer."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, Union

try:
    from litellm import completion
except ImportError:
    # Fallback/Mock for environments without litellm (though we should have it)
    completion = None

class LLMService:
    """Wrapper for LLM calls with JSON enforcement."""

    def __init__(self, model: str = "gpt-4-turbo", temperature: float = 0.0):
        self.model = model
        self.temperature = temperature

    def call(self, system_prompt: str, user_prompt: str, json_mode: bool = False) -> Union[str, Dict[str, Any]]:
        if completion is None:
            raise ImportError("litellm is not installed.")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        kwargs = {"model": self.model, "messages": messages, "temperature": self.temperature}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = completion(**kwargs)
        content = response.choices[0].message.content.strip()

        if json_mode:
            return self._parse_json(content)
        return content

    def _parse_json(self, content: str) -> Dict[str, Any]:
        """Robust JSON parsing."""
        clean = content
        # Remove markdown code blocks if present
        if clean.startswith("```json"):
            clean = clean[7:]
        if clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]

        try:
            return json.loads(clean.strip())
        except json.JSONDecodeError:
            # Simple fallback: try to find the first { and last }
            try:
                start = clean.index("{")
                end = clean.rindex("}") + 1
                return json.loads(clean[start:end])
            except Exception:
                # Give up and return a wrapper
                return {"error": "Failed to parse JSON", "raw": content}
