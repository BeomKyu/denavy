"""RC5: FSM 라우터 테스트

검증 항목:
  - Protocol 준수
  - 정상 상태 전이 (IDLE → PLANNING → CODING → ...)
  - 역할 침범 차단 (CODER가 PLANNING → CODING 시도)
  - 금지된 전이 차단 (IDLE → TESTING 등)
  - 정보 접근 화이트리스트 (역할별 데이터 필터링)
  - 가드 조건 검증
  - FSM 리셋
"""

import pytest

from denavy.protocols import DefenseVerdict, RootCauseDefense
from denavy.rc5_tom_deficit.fsm_router import (
    AgentRole,
    FSMRouter,
    FSMRouterDefense,
    PipelineState,
    filter_context_for_role,
)


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def router():
    r = FSMRouter()
    r.setup_default_pipeline()
    return r


@pytest.fixture
def defense(router):
    return FSMRouterDefense(router)


# ──────────────────────────────────────────────
# Protocol 준수
# ──────────────────────────────────────────────

class TestProtocolCompliance:
    def test_implements_protocol(self, defense):
        assert isinstance(defense, RootCauseDefense)

    def test_root_cause_id(self, defense):
        assert defense.root_cause_id == 5

    def test_target_defects(self, defense):
        assert defense.target_defects == [16, 17]


# ──────────────────────────────────────────────
# 정상 전이
# ──────────────────────────────────────────────

class TestNormalTransitions:
    def test_idle_to_planning(self, router):
        ok, _ = router.transition(AgentRole.PLANNER, PipelineState.PLANNING)
        assert ok
        assert router.state == PipelineState.PLANNING

    def test_full_pipeline(self, router):
        """IDLE → PLANNING → CODING → REVIEWING → TESTING → COMPLETED."""
        steps = [
            (AgentRole.PLANNER, PipelineState.PLANNING),
            (AgentRole.CODER, PipelineState.CODING),
            (AgentRole.REVIEWER, PipelineState.REVIEWING),   # CODING → REVIEWING
            (AgentRole.TESTER, PipelineState.TESTING),        # REVIEWING → TESTING
            (AgentRole.TESTER, PipelineState.COMPLETED),      # TESTING → COMPLETED
        ]
        for role, target in steps:
            ok, reason = router.transition(role, target)
            assert ok, f"전이 실패: {reason}"
        assert router.state == PipelineState.COMPLETED

    def test_history_tracked(self, router):
        router.transition(AgentRole.PLANNER, PipelineState.PLANNING)
        assert len(router.context.history) == 1
        assert router.context.history[0]["to"] == "planning"


# ──────────────────────────────────────────────
# 역할 침범 차단 (결함 16)
# ──────────────────────────────────────────────

class TestRoleInvasion:
    def test_coder_cannot_start_planning(self, router):
        """CODER가 IDLE → PLANNING 전이 시도 → 거부."""
        ok, reason = router.transition(AgentRole.CODER, PipelineState.PLANNING)
        assert not ok
        assert "역할 침범" in reason

    def test_tester_cannot_start_coding(self, router):
        router.transition(AgentRole.PLANNER, PipelineState.PLANNING)
        ok, reason = router.transition(AgentRole.TESTER, PipelineState.CODING)
        assert not ok
        assert "역할 침범" in reason

    def test_defense_rejects_role_invasion(self, defense, router):
        result = defense.validate({
            "role": "coder",
            "target_state": "planning",
        })
        assert result.rejected
        assert "역할 침범" in result.reason


# ──────────────────────────────────────────────
# 금지된 전이 차단
# ──────────────────────────────────────────────

class TestForbiddenTransitions:
    def test_idle_to_testing_impossible(self, router):
        ok, reason = router.transition(AgentRole.TESTER, PipelineState.TESTING)
        assert not ok
        assert "금지된 전이" in reason

    def test_defense_rejects_forbidden_transition(self, defense):
        result = defense.validate({
            "role": "tester",
            "target_state": "testing",
        })
        assert result.rejected


# ──────────────────────────────────────────────
# 정보 접근 제어 (결함 17)
# ──────────────────────────────────────────────

class TestInformationHiding:
    def test_filter_for_coder(self):
        data = {
            "task_description": "기능 추가",
            "target_files": ["main.py"],
            "deploy_config": {"host": "prod"},  # CODER에게 비공개
        }
        filtered = filter_context_for_role(data, AgentRole.CODER)
        assert "task_description" in filtered
        assert "target_files" in filtered
        assert "deploy_config" not in filtered

    def test_filter_for_tester(self):
        data = {
            "code_changes": ["diff..."],
            "architecture": {"modules": []},  # TESTER에게 비공개
        }
        filtered = filter_context_for_role(data, AgentRole.TESTER)
        assert "code_changes" in filtered
        assert "architecture" not in filtered

    def test_defense_rejects_forbidden_data_access(self, defense, router):
        # PLANNER가 deploy_config 접근 시도
        result = defense.validate({
            "role": "planner",
            "data_keys": ["requirements", "deploy_config"],
        })
        assert result.rejected
        assert "정보 접근 위반" in result.reason

    def test_defense_allows_permitted_data_access(self, defense, router):
        result = defense.validate({
            "role": "planner",
            "data_keys": ["requirements", "architecture"],
        })
        assert result.passed


# ──────────────────────────────────────────────
# 가드 조건
# ──────────────────────────────────────────────

class TestGuardCondition:
    def test_guard_blocks_transition(self):
        router = FSMRouter()
        router.add_transition(
            PipelineState.IDLE,
            PipelineState.PLANNING,
            AgentRole.PLANNER,
            guard=lambda: False,  # 항상 거부
        )
        ok, reason = router.transition(AgentRole.PLANNER, PipelineState.PLANNING)
        assert not ok
        assert "가드 조건" in reason

    def test_guard_allows_transition(self):
        router = FSMRouter()
        router.add_transition(
            PipelineState.IDLE,
            PipelineState.PLANNING,
            AgentRole.PLANNER,
            guard=lambda: True,
        )
        ok, _ = router.transition(AgentRole.PLANNER, PipelineState.PLANNING)
        assert ok


# ──────────────────────────────────────────────
# 기타
# ──────────────────────────────────────────────

class TestEdgeCases:
    def test_reset(self, router):
        router.transition(AgentRole.PLANNER, PipelineState.PLANNING)
        router.reset()
        assert router.state == PipelineState.IDLE

    def test_invalid_role_rejected(self, defense):
        result = defense.validate({"role": "hacker", "target_state": "idle"})
        assert result.rejected

    def test_invalid_state_rejected(self, defense):
        result = defense.validate({"role": "planner", "target_state": "nonexistent"})
        assert result.rejected

    def test_invalid_input_rejected(self, defense):
        result = defense.validate("not a dict")
        assert result.rejected

    def test_allowed_transitions_query(self, router):
        allowed = router.get_allowed_transitions(AgentRole.PLANNER)
        assert len(allowed) == 1
        assert allowed[0].to_state == PipelineState.PLANNING
