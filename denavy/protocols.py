"""
공통 Protocol 정의
━━━━━━━━━━━━━━━━━
모든 근본 원인(RC) 방어 모듈이 구현해야 하는 인터페이스.
구현체를 자유롭게 교체할 수 있도록 Protocol 기반 추상화를 제공한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


# ──────────────────────────────────────────────
# 공통 열거형 / 데이터 클래스
# ──────────────────────────────────────────────

class DefenseVerdict(str, Enum):
    """방어 모듈의 판정 결과."""
    PASS = "pass"          # 검증 통과
    REJECT = "reject"      # 즉각 거부
    NEEDS_REVIEW = "review" # 추가 검토 필요


@dataclass(frozen=True)
class DefenseResult:
    """방어 모듈의 판정 결과 객체.

    Attributes:
        verdict: 판정 결과 (pass / reject / review)
        module_name: 판정을 내린 모듈 이름
        root_cause_id: 근본 원인 번호 (1~9)
        reason: 거부 또는 검토 사유
        details: 추가 상세 정보 (반례, 에러 모델 등)
    """
    verdict: DefenseVerdict
    module_name: str
    root_cause_id: int
    reason: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.verdict == DefenseVerdict.PASS

    @property
    def rejected(self) -> bool:
        return self.verdict == DefenseVerdict.REJECT


# ──────────────────────────────────────────────
# 핵심 Protocol 정의
# ──────────────────────────────────────────────

@runtime_checkable
class RootCauseDefense(Protocol):
    """모든 근본 원인 방어 모듈의 공통 인터페이스.

    각 RC(Root Cause) 모듈은 이 Protocol을 구현하여
    파이프라인에 플러그인 방식으로 장착된다.
    구현체를 교체해도 파이프라인 코드는 변경할 필요가 없다.

    Attributes:
        root_cause_id: 이 모듈이 방어하는 근본 원인 번호 (1~9)
        target_defects: 이 모듈이 억압하는 표면적 결함 번호 목록
    """

    @property
    def root_cause_id(self) -> int: ...

    @property
    def target_defects(self) -> list[int]: ...

    def validate(self, input_data: Any) -> DefenseResult:
        """입력 데이터를 검증하고 판정 결과를 반환한다.

        Args:
            input_data: 검증할 데이터 (모듈마다 타입이 다름)

        Returns:
            DefenseResult: 판정 결과
        """
        ...

    def is_enabled(self) -> bool:
        """이 방어 모듈이 현재 활성 상태인지 반환."""
        ...


@runtime_checkable
class LLMProvider(Protocol):
    """LLM 백엔드 추상화.

    litellm 기반으로 구현되며, 모델명만 교체하면
    OpenAI / Anthropic / Ollama 등 어떤 백엔드든 사용 가능.
    """

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        **kwargs: Any,
    ) -> str:
        """자연어 텍스트 응답을 생성한다."""
        ...

    async def complete_structured(
        self,
        messages: list[dict[str, str]],
        model: str,
        response_model: type,
        **kwargs: Any,
    ) -> Any:
        """Pydantic BaseModel 형태의 구조화된 응답을 강제한다."""
        ...


@runtime_checkable
class SandboxProvider(Protocol):
    """코드 실행 환경 추상화.

    Deno Deploy(클라우드) 또는 로컬 Deno CLI로 교체 가능.
    """

    async def execute(
        self,
        code: str,
        allowed_hosts: list[str] | None = None,
        secrets_map: dict[str, str] | None = None,
        timeout_seconds: int = 30,
    ) -> "ExecutionResult":
        """격리된 샌드박스에서 코드를 실행한다."""
        ...


@dataclass(frozen=True)
class ExecutionResult:
    """샌드박스 실행 결과."""
    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
