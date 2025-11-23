"""LiteLLM-powered helpers with graceful fallbacks."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from rich.console import Console
from rich.panel import Panel
from denavy_common import JudgeDecision

from litellm import completion
from litellm.utils import Choices

# '진화': default_template.toml의 강력한 프롬프트로 통일 및 구조 강화
DEFAULT_DECISION_PROMPT = """
You are the Veto Engine for Denavy.
Your task is to review the proposed execution plan against the user's request.

Output Format:
You must output a SINGLE valid JSON object. 
Do NOT add any markdown formatting (no ```json blocks).
Do NOT add any text before or after the JSON.

JSON Structure:
{
  "approved": boolean, // true if the plan effectively addresses the user's discomfort. false otherwise.
  "reason": "string",  // A concise explanation of your decision (max 1 sentence).
  "recommended_template": "string" // Optional: If rejecting, suggest a better template/plugin name from the 'Available Tools' list. null if no better option.
}

Criteria:
- If the plan is logical and relevant to the user's input, approve it.
- If the plan is harmful, irrelevant, or fundamentally flawed, deny it.
- If you deny it, check the 'Available Tools' list provided in the prompt and recommend a safer or more appropriate template/plugin name in 'recommended_template'.
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
        # '진화': 모델이 지원한다면 JSON 모드 강제 (OpenAI 등)
        json_kwargs["response_format"] = {"type": "json_object"}

        try:
            response = completion(model=self.model, messages=messages, **json_kwargs)
            message = _extract_first_message(response.choices)
            
            # '진화': 마크다운 코드 블록이 섞여 있을 경우 제거하는 방어 로직 추가
            cleaned_message = message.strip()
            if cleaned_message.startswith("```json"):
                cleaned_message = cleaned_message[7:]
            if cleaned_message.startswith("```"):
                cleaned_message = cleaned_message[3:]
            if cleaned_message.endswith("```"):
                cleaned_message = cleaned_message[:-3]
                
            return json.loads(cleaned_message.strip())
        
        except json.JSONDecodeError as exc:
            # 실패 시에도 원본 메시지를 raw 필드에 담아 디버깅 용이하게 함
            return {"approved": True, "reason": f"Judge failed JSON parsing ({exc}), defaulting to approve.", "raw": message}
        except Exception as exc:
            self.console.print(Panel.fit(f"Judge invocation failed: {exc}", title="Veto", style="red"))
            return JudgeDecision(approved=True, reason="Judge unavailable; fallback to approve").model_dump()


def _extract_first_message(choices: Choices) -> str:
    if not choices:
        return "{}"
    message = choices[0].get("message", {})
    return message.get("content", "{}")
