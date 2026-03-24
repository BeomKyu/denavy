"""
RC4: 샌드박스 OCap(Object-Capability) 실행 환경
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
근본 원인 4 — 인식론적 단절 (Epistemic Disconnect)

억압 결함:
  결함 6 — 환각된 도구 호출: 존재하지 않는 API를 호출하려는 시도
  결함 9 — 허위 근거: 실재하지 않는 데이터를 인용
  결함 15 — 자원 남용: 무제한 API 호출, 메모리/CPU 폭주

핵심 원리:
  에이전트가 사용할 수 있는 도구(Tool)를 명시적 화이트리스트로 제한.
  OCap(Object-Capability) 모델: 도구에 대한 접근 권한을 능력 토큰으로 관리.
  - 도구 등록소(ToolRegistry)에 등록된 도구만 호출 가능
  - 미등록 도구 호출 = 환각(결함 6) → 즉각 거부
  - 호출 횟수/속도 제한 = 자원 남용(결함 15) 방어
  - 실행 결과의 Schema 검증 = 허위 근거(결함 9) 방어

Deno 배포 환경이 미구축된 개발 단계에서는
도구 등록소 + 호출 감사(Audit) + 쿼터 관리로 OCap를 에뮬레이트.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from denavy.protocols import DefenseResult, DefenseVerdict, RootCauseDefense

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 도구(Tool) 데이터 모델
# ──────────────────────────────────────────────

@dataclass
class ToolCapability:
    """에이전트에게 부여된 도구 사용 능력(Capability).

    OCap 모델: 능력 토큰이 있어야만 도구를 호출할 수 있다.
    """
    tool_name: str
    description: str
    max_calls_per_minute: int = 60
    max_calls_total: int = 1000
    required_params: list[str] = field(default_factory=list)
    handler: Callable[..., Any] | None = None  # 실제 도구 핸들러

    # 사용량 추적
    call_count: int = 0
    last_call_time: float = 0.0
    call_timestamps: list[float] = field(default_factory=list)


@dataclass
class ToolCallAudit:
    """도구 호출 감사 기록."""
    tool_name: str
    timestamp: float
    authorized: bool
    reason: str
    params: dict[str, Any] = field(default_factory=dict)


# ──────────────────────────────────────────────
# 도구 등록소 (Tool Registry)
# ──────────────────────────────────────────────

class ToolRegistry:
    """에이전트가 사용할 수 있는 도구의 등록소.

    미등록 도구 호출은 환각(결함 6)으로 간주하여 차단.
    등록된 도구만 화이트리스트 방식으로 허용.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolCapability] = {}
        self._audit_log: list[ToolCallAudit] = []

    def register(self, capability: ToolCapability) -> None:
        """도구를 등록한다."""
        self._tools[capability.tool_name] = capability
        logger.info(f"RC4: 도구 등록 '{capability.tool_name}'")

    def is_registered(self, tool_name: str) -> bool:
        """도구가 등록되어 있는가."""
        return tool_name in self._tools

    def get(self, tool_name: str) -> ToolCapability | None:
        return self._tools.get(tool_name)

    @property
    def registered_tools(self) -> list[str]:
        return list(self._tools.keys())

    @property
    def audit_log(self) -> list[ToolCallAudit]:
        return self._audit_log.copy()

    def authorize_call(
        self,
        tool_name: str,
        params: dict[str, Any] | None = None,
    ) -> tuple[bool, str]:
        """도구 호출을 인가한다.

        Args:
            tool_name: 호출할 도구 이름
            params: 호출 파라미터

        Returns:
            (인가 여부, 사유)
        """
        params = params or {}
        now = time.time()

        # 1. 화이트리스트 검사 (환각 방어)
        if not self.is_registered(tool_name):
            audit = ToolCallAudit(
                tool_name=tool_name,
                timestamp=now,
                authorized=False,
                reason=f"환각 도구 호출: '{tool_name}'은 등록되지 않음",
                params=params,
            )
            self._audit_log.append(audit)
            return (False, audit.reason)

        cap = self._tools[tool_name]

        # 2. 총 호출 횟수 제한 (자원 남용 방어)
        if cap.call_count >= cap.max_calls_total:
            audit = ToolCallAudit(
                tool_name=tool_name,
                timestamp=now,
                authorized=False,
                reason=(
                    f"총 호출 상한 초과: '{tool_name}' "
                    f"({cap.call_count}/{cap.max_calls_total})"
                ),
                params=params,
            )
            self._audit_log.append(audit)
            return (False, audit.reason)

        # 3. 분당 호출 속도 제한 (자원 남용 방어)
        one_minute_ago = now - 60.0
        recent_calls = [
            t for t in cap.call_timestamps if t > one_minute_ago
        ]
        if len(recent_calls) >= cap.max_calls_per_minute:
            audit = ToolCallAudit(
                tool_name=tool_name,
                timestamp=now,
                authorized=False,
                reason=(
                    f"속도 제한 초과: '{tool_name}' "
                    f"({len(recent_calls)}/{cap.max_calls_per_minute}/분)"
                ),
                params=params,
            )
            self._audit_log.append(audit)
            return (False, audit.reason)

        # 4. 필수 파라미터 검사 (허위 근거 방어)
        missing = [p for p in cap.required_params if p not in params]
        if missing:
            audit = ToolCallAudit(
                tool_name=tool_name,
                timestamp=now,
                authorized=False,
                reason=f"필수 파라미터 누락: {missing}",
                params=params,
            )
            self._audit_log.append(audit)
            return (False, audit.reason)

        # 5. 인가 성공
        cap.call_count += 1
        cap.last_call_time = now
        cap.call_timestamps.append(now)

        audit = ToolCallAudit(
            tool_name=tool_name,
            timestamp=now,
            authorized=True,
            reason="인가 성공",
            params=params,
        )
        self._audit_log.append(audit)
        return (True, "인가 성공")


# ──────────────────────────────────────────────
# RC4 방어 모듈
# ──────────────────────────────────────────────

class SandboxOCapDefense:
    """RC4: 샌드박스 OCap 방어 모듈.

    에이전트의 도구 호출 시도를 검증한다.

    이 모듈은 RootCauseDefense Protocol을 구현한다.

    validate()는 다음을 검증:
      1. 호출 대상 도구가 등록소에 존재하는가 (환각 방어)
      2. 호출 횟수/속도가 쿼터 내인가 (자원 남용 방어)
      3. 필수 파라미터가 제공되었는가 (허위 근거 방어)
    """

    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self._registry = registry or ToolRegistry()

    @property
    def root_cause_id(self) -> int:
        return 4

    @property
    def target_defects(self) -> list[int]:
        return [6, 9, 15]

    def is_enabled(self) -> bool:
        return True

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    def validate(self, input_data: Any) -> DefenseResult:
        """도구 호출을 검증한다.

        Args:
            input_data: dict with:
              - "tool_name": 호출할 도구 이름
              - "params": 호출 파라미터 (optional)

        Returns:
            DefenseResult: 검증 결과
        """
        if not isinstance(input_data, dict):
            return DefenseResult(
                verdict=DefenseVerdict.REJECT,
                module_name="RC4_SandboxOCap",
                root_cause_id=4,
                reason=f"입력이 dict가 아님: {type(input_data).__name__}",
            )

        tool_name = input_data.get("tool_name", "")
        if not tool_name:
            return DefenseResult(
                verdict=DefenseVerdict.REJECT,
                module_name="RC4_SandboxOCap",
                root_cause_id=4,
                reason="tool_name이 비어 있음",
            )

        params = input_data.get("params", {})
        authorized, reason = self._registry.authorize_call(tool_name, params)

        if not authorized:
            return DefenseResult(
                verdict=DefenseVerdict.REJECT,
                module_name="RC4_SandboxOCap",
                root_cause_id=4,
                reason=reason,
                details={
                    "tool_name": tool_name,
                    "registered_tools": self._registry.registered_tools,
                },
            )

        return DefenseResult(
            verdict=DefenseVerdict.PASS,
            module_name="RC4_SandboxOCap",
            root_cause_id=4,
            reason=f"도구 호출 인가: {tool_name}",
            details={"tool_name": tool_name},
        )
