"""
LLM Provider — litellm + instructor 래핑
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
protocols.py 의 LLMProvider Protocol 구현체.

litellm을 통해 100+ LLM 프로바이더를 동일 API로 호출.
instructor를 통해 Pydantic BaseModel 형태의 구조화된 응답 강제.

사용법:
    from denavy.litellm_provider import LiteLLMProvider
    provider = LiteLLMProvider()
    text = await provider.complete(messages, model="gpt-4o-mini")
    payload = await provider.complete_structured(messages, model, IntentionPayload)
"""

from __future__ import annotations

import logging
import os
from typing import Any

import instructor
import litellm

from denavy.config import settings

logger = logging.getLogger(__name__)


class LiteLLMProvider:
    """LLMProvider Protocol 구현체.

    config.py의 api_key, api_base, default_model을 사용.
    환경변수 OPENAI_API_KEY, ANTHROPIC_API_KEY 등도 litellm이 자동 감지.
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        api_base: str | None = None,
    ) -> None:
        self._model = model or settings.default_model
        self._api_key = api_key or settings.api_key
        self._api_base = api_base or settings.api_base or None

        # litellm 글로벌 설정
        if self._api_key:
            # litellm은 프로바이더별 환경변수를 자동 감지하지만,
            # DENAVY_API_KEY로 통합 설정된 경우 직접 세팅
            os.environ.setdefault("OPENAI_API_KEY", self._api_key)
            os.environ.setdefault("ANTHROPIC_API_KEY", self._api_key)
            os.environ.setdefault("GEMINI_API_KEY", self._api_key)

        # litellm 설정
        litellm.drop_params = True  # 미지원 파라미터 자동 제거

        # instructor 클라이언트 (구조화 응답용)
        self._instructor_client = instructor.from_litellm(litellm.completion)

        logger.info(f"LLMProvider 초기화: model={self._model}")

    @property
    def model(self) -> str:
        return self._model

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        **kwargs: Any,
    ) -> str:
        """자연어 텍스트 응답을 생성한다.

        Args:
            messages: [{"role": "user", "content": "..."}]
            model: 모델명 (None이면 기본 모델)

        Returns:
            LLM의 텍스트 응답
        """
        target_model = model or self._model
        call_kwargs: dict[str, Any] = {
            "model": target_model,
            "messages": messages,
        }
        if self._api_base:
            call_kwargs["api_base"] = self._api_base
        call_kwargs.update(kwargs)

        response = await litellm.acompletion(**call_kwargs)
        content = response.choices[0].message.content or ""
        return content

    async def complete_structured(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        response_model: type | None = None,
        **kwargs: Any,
    ) -> Any:
        """Pydantic BaseModel 형태의 구조화된 응답을 강제한다.

        instructor가 LLM 출력을 response_model로 파싱.
        파싱 실패 시 자동 재시도 (max_retries=3).

        Args:
            messages: 대화 메시지
            model: 모델명
            response_model: Pydantic BaseModel 타입

        Returns:
            response_model의 인스턴스
        """
        target_model = model or self._model
        call_kwargs: dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "response_model": response_model,
            "max_retries": 3,
        }
        if self._api_base:
            call_kwargs["api_base"] = self._api_base
        call_kwargs.update(kwargs)

        result = self._instructor_client.chat.completions.create(**call_kwargs)
        return result

    def check_connection(self) -> dict[str, Any]:
        """설정 상태를 확인한다 (실제 API 호출 없이).

        Returns:
            설정 상태 dict
        """
        has_key = bool(self._api_key)
        has_env_openai = bool(os.environ.get("OPENAI_API_KEY"))
        has_env_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))

        return {
            "model": self._model,
            "api_key_set": has_key,
            "api_base": self._api_base or "(default)",
            "env_openai_key": has_env_openai,
            "env_anthropic_key": has_env_anthropic,
            "ready": has_key or has_env_openai or has_env_anthropic,
        }
