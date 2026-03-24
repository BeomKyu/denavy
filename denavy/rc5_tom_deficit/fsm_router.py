"""
RC5: 결정론적 FSM 라우터 — 에이전트 역할 경계 강제
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
근본 원인 5 — 마음 이론(Theory of Mind) 결핍

억압 결함:
  결함 16 — 역할 침범: 에이전트가 다른 에이전트의 영역 침투
  결함 17 — 정보 은닉 실패: 불필요한 정보를 에이전트에게 노출

핵심 원리:
  에이전트들 간의 자유로운 P2P 통신을 단절시키고,
  중앙 집중형 유한 상태 기계(FSM)가 모든 상태 전이를 통제.
  - 각 에이전트는 자기 역할(Role)에 해당하는 상태에서만 행동 가능
  - 전이 규칙 외의 상태 전환은 물리적으로 불가
  - 정보는 역할별 허용 범위 내에서만 공유

LangGraph의 StateGraph 패턴을 차용하되,
LLM 호출 없이 순수 결정론적 상태 전이만 관리.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from denavy.protocols import DefenseResult, DefenseVerdict, RootCauseDefense

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 에이전트 역할 및 상태 정의
# ──────────────────────────────────────────────

class AgentRole(str, Enum):
    """에이전트 역할. 각 역할은 허용된 행동만 수행 가능."""
    PLANNER = "planner"        # 계획 수립
    CODER = "coder"            # 코드 생성/수정
    REVIEWER = "reviewer"      # 코드 검토
    TESTER = "tester"          # 테스트 실행
    DEPLOYER = "deployer"      # 배포


class PipelineState(str, Enum):
    """파이프라인 상태. FSM의 노드."""
    IDLE = "idle"
    PLANNING = "planning"
    CODING = "coding"
    REVIEWING = "reviewing"
    TESTING = "testing"
    DEPLOYING = "deploying"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TransitionRule:
    """상태 전이 규칙."""
    from_state: PipelineState
    to_state: PipelineState
    required_role: AgentRole
    guard: Callable[..., bool] | None = None  # 전이 조건 함수
    description: str = ""


@dataclass
class FSMContext:
    """FSM의 현재 컨텍스트 (공유 상태)."""
    current_state: PipelineState = PipelineState.IDLE
    current_role: AgentRole | None = None
    task_id: str = ""
    history: list[dict[str, Any]] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)


# ──────────────────────────────────────────────
# 역할별 정보 접근 제어
# ──────────────────────────────────────────────

# 각 역할이 접근할 수 있는 데이터 키 화이트리스트
_ROLE_ACCESS: dict[AgentRole, set[str]] = {
    AgentRole.PLANNER: {"requirements", "architecture", "task_description"},
    AgentRole.CODER: {"task_description", "target_files", "code_slices", "test_results"},
    AgentRole.REVIEWER: {"code_changes", "architecture", "conventions"},
    AgentRole.TESTER: {"code_changes", "test_commands", "test_results"},
    AgentRole.DEPLOYER: {"build_artifacts", "deploy_config"},
}


def filter_context_for_role(
    data: dict[str, Any], role: AgentRole
) -> dict[str, Any]:
    """역할에 허용된 키만 필터링하여 반환한다.

    정보 은닉(결함 17 방어): 에이전트에게 불필요한 정보를 노출하지 않음.
    """
    allowed_keys = _ROLE_ACCESS.get(role, set())
    return {k: v for k, v in data.items() if k in allowed_keys}


# ──────────────────────────────────────────────
# FSM 라우터
# ──────────────────────────────────────────────

class FSMRouter:
    """결정론적 유한 상태 기계(FSM) 라우터.

    에이전트의 행동을 사전 정의된 상태 전이 규칙으로만 제한.
    규칙에 없는 전이는 물리적으로 불가능.

    사용법:
        router = FSMRouter()
        router.add_transition(
            PipelineState.IDLE,
            PipelineState.PLANNING,
            AgentRole.PLANNER,
        )

        # 전이 시도
        ok, reason = router.transition(AgentRole.PLANNER, PipelineState.PLANNING)
    """

    def __init__(self) -> None:
        self._transitions: list[TransitionRule] = []
        self._context = FSMContext()

    @property
    def state(self) -> PipelineState:
        return self._context.current_state

    @property
    def context(self) -> FSMContext:
        return self._context

    def add_transition(
        self,
        from_state: PipelineState,
        to_state: PipelineState,
        required_role: AgentRole,
        guard: Callable[..., bool] | None = None,
        description: str = "",
    ) -> None:
        """상태 전이 규칙을 등록한다."""
        self._transitions.append(TransitionRule(
            from_state=from_state,
            to_state=to_state,
            required_role=required_role,
            guard=guard,
            description=description,
        ))

    def setup_default_pipeline(self) -> None:
        """기본 개발 파이프라인 전이 규칙을 설정한다.

        IDLE → PLANNING → CODING → REVIEWING → TESTING → COMPLETED
                                                    ↓
                                                  FAILED
        """
        rules = [
            (PipelineState.IDLE, PipelineState.PLANNING, AgentRole.PLANNER),
            (PipelineState.PLANNING, PipelineState.CODING, AgentRole.CODER),
            (PipelineState.CODING, PipelineState.REVIEWING, AgentRole.REVIEWER),
            (PipelineState.REVIEWING, PipelineState.CODING, AgentRole.REVIEWER),  # 수정 요청
            (PipelineState.REVIEWING, PipelineState.TESTING, AgentRole.TESTER),
            (PipelineState.TESTING, PipelineState.COMPLETED, AgentRole.TESTER),
            (PipelineState.TESTING, PipelineState.FAILED, AgentRole.TESTER),
            (PipelineState.FAILED, PipelineState.CODING, AgentRole.CODER),  # 재시도
        ]
        for from_s, to_s, role in rules:
            self.add_transition(from_s, to_s, role)

    def transition(
        self,
        role: AgentRole,
        target_state: PipelineState,
    ) -> tuple[bool, str]:
        """상태 전이를 시도한다.

        Args:
            role: 전이를 요청하는 에이전트의 역할
            target_state: 목표 상태

        Returns:
            (성공 여부, 사유 문자열)
        """
        current = self._context.current_state

        # 규칙 검색
        matching = [
            t for t in self._transitions
            if t.from_state == current
            and t.to_state == target_state
            and t.required_role == role
        ]

        if not matching:
            # 역할 침범 감지
            wrong_role = [
                t for t in self._transitions
                if t.from_state == current
                and t.to_state == target_state
            ]
            if wrong_role:
                expected = wrong_role[0].required_role
                return (
                    False,
                    f"역할 침범: {role.value}는 "
                    f"{current.value}→{target_state.value} 전이 불가. "
                    f"필요 역할: {expected.value}",
                )

            return (
                False,
                f"금지된 전이: {current.value}→{target_state.value} "
                f"(규칙에 정의되지 않음)",
            )

        rule = matching[0]

        # 가드 조건 확인
        if rule.guard and not rule.guard():
            return (
                False,
                f"가드 조건 미충족: {current.value}→{target_state.value}",
            )

        # 전이 실행
        self._context.history.append({
            "from": current.value,
            "to": target_state.value,
            "role": role.value,
            "timestamp": time.time(),
        })
        self._context.current_state = target_state
        self._context.current_role = role

        logger.info(
            f"RC5 FSM: {current.value} → {target_state.value} "
            f"(role={role.value})"
        )
        return (True, f"{current.value} → {target_state.value}")

    def get_allowed_transitions(
        self, role: AgentRole | None = None
    ) -> list[TransitionRule]:
        """현재 상태에서 가능한 전이 목록을 반환한다."""
        current = self._context.current_state
        return [
            t for t in self._transitions
            if t.from_state == current
            and (role is None or t.required_role == role)
        ]

    def reset(self) -> None:
        """FSM을 초기 상태로 리셋한다."""
        self._context = FSMContext()


# ──────────────────────────────────────────────
# RC5 방어 모듈
# ──────────────────────────────────────────────

class FSMRouterDefense:
    """RC5: FSM 라우터 방어 모듈.

    에이전트의 행동이 FSM 규칙에 부합하는지 검증한다.

    이 모듈은 RootCauseDefense Protocol을 구현한다.

    validate()는 다음을 검증:
      1. 에이전트의 역할이 현재 상태에서 행동을 허용하는가
      2. 요청된 전이가 규칙에 정의되어 있는가
      3. 정보 접근이 역할 화이트리스트 범위 내인가
    """

    def __init__(self, router: FSMRouter) -> None:
        self._router = router

    @property
    def root_cause_id(self) -> int:
        return 5

    @property
    def target_defects(self) -> list[int]:
        return [16, 17]

    def is_enabled(self) -> bool:
        return True

    def validate(self, input_data: Any) -> DefenseResult:
        """에이전트 행동의 FSM 규칙 준수를 검증한다.

        Args:
            input_data: dict with:
              - "role": AgentRole 값 (str)
              - "target_state": PipelineState 값 (str)
              - "data_keys": 접근 요청 데이터 키 목록 (optional)

        Returns:
            DefenseResult: 검증 결과
        """
        if not isinstance(input_data, dict):
            return DefenseResult(
                verdict=DefenseVerdict.REJECT,
                module_name="RC5_FSMRouter",
                root_cause_id=5,
                reason=f"입력이 dict가 아님: {type(input_data).__name__}",
            )

        try:
            role = AgentRole(input_data.get("role", ""))
        except ValueError:
            return DefenseResult(
                verdict=DefenseVerdict.REJECT,
                module_name="RC5_FSMRouter",
                root_cause_id=5,
                reason=f"알 수 없는 역할: {input_data.get('role')}",
            )

        target = input_data.get("target_state", "")
        if target:
            try:
                target_state = PipelineState(target)
            except ValueError:
                return DefenseResult(
                    verdict=DefenseVerdict.REJECT,
                    module_name="RC5_FSMRouter",
                    root_cause_id=5,
                    reason=f"알 수 없는 상태: {target}",
                )

            ok, reason = self._router.transition(role, target_state)
            if not ok:
                return DefenseResult(
                    verdict=DefenseVerdict.REJECT,
                    module_name="RC5_FSMRouter",
                    root_cause_id=5,
                    reason=reason,
                    details={
                        "current_state": self._router.state.value,
                        "requested_state": target_state.value,
                        "role": role.value,
                    },
                )

        # 정보 접근 검증 (결함 17)
        requested_keys = input_data.get("data_keys", [])
        if requested_keys:
            allowed = _ROLE_ACCESS.get(role, set())
            forbidden = [k for k in requested_keys if k not in allowed]
            if forbidden:
                return DefenseResult(
                    verdict=DefenseVerdict.REJECT,
                    module_name="RC5_FSMRouter",
                    root_cause_id=5,
                    reason=(
                        f"정보 접근 위반: {role.value} 역할이 "
                        f"금지된 데이터 접근 시도: {forbidden}"
                    ),
                    details={
                        "role": role.value,
                        "forbidden_keys": forbidden,
                        "allowed_keys": list(allowed),
                    },
                )

        return DefenseResult(
            verdict=DefenseVerdict.PASS,
            module_name="RC5_FSMRouter",
            root_cause_id=5,
            reason="FSM 규칙 및 정보 접근 검증 통과",
            details={
                "current_state": self._router.state.value,
                "role": role.value,
            },
        )
