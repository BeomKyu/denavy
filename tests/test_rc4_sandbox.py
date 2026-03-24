"""RC4: 샌드박스 OCap 테스트

검증 항목:
  - Protocol 준수
  - 등록된 도구 호출 인가
  - 미등록 도구 호출 차단 (환각 방어)
  - 총 호출 횟수 제한 (자원 남용)
  - 분당 호출 속도 제한 (자원 남용)
  - 필수 파라미터 검증 (허위 근거 방어)
  - 감사(Audit) 로그 기록
"""

import time

import pytest

from denavy.protocols import DefenseVerdict, RootCauseDefense
from denavy.rc4_epistemic_disconnect.sandbox_ocap import (
    SandboxOCapDefense,
    ToolCapability,
    ToolRegistry,
)


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def registry():
    reg = ToolRegistry()
    reg.register(ToolCapability(
        tool_name="read_file",
        description="파일 읽기",
        max_calls_per_minute=10,
        max_calls_total=100,
        required_params=["path"],
    ))
    reg.register(ToolCapability(
        tool_name="search_code",
        description="코드 검색",
        max_calls_per_minute=20,
        max_calls_total=500,
    ))
    return reg


@pytest.fixture
def defense(registry):
    return SandboxOCapDefense(registry=registry)


# ──────────────────────────────────────────────
# Protocol 준수
# ──────────────────────────────────────────────

class TestProtocolCompliance:
    def test_implements_protocol(self, defense):
        assert isinstance(defense, RootCauseDefense)

    def test_root_cause_id(self, defense):
        assert defense.root_cause_id == 4

    def test_target_defects(self, defense):
        assert defense.target_defects == [6, 9, 15]


# ──────────────────────────────────────────────
# 정상 도구 호출
# ──────────────────────────────────────────────

class TestNormalCalls:
    def test_registered_tool_authorized(self, defense):
        result = defense.validate({
            "tool_name": "read_file",
            "params": {"path": "/src/main.py"},
        })
        assert result.passed

    def test_no_required_params_tool(self, defense):
        """필수 파라미터 없는 도구는 params 없이 호출 가능."""
        result = defense.validate({"tool_name": "search_code"})
        assert result.passed


# ──────────────────────────────────────────────
# 환각 방어 (결함 6)
# ──────────────────────────────────────────────

class TestHallucinationDefense:
    def test_unregistered_tool_rejected(self, defense):
        """미등록 도구 호출 = 환각."""
        result = defense.validate({"tool_name": "deploy_to_production"})
        assert result.rejected
        assert "환각" in result.reason

    def test_missing_tool_name_rejected(self, defense):
        result = defense.validate({"tool_name": ""})
        assert result.rejected

    def test_invalid_input_rejected(self, defense):
        result = defense.validate("not a dict")
        assert result.rejected


# ──────────────────────────────────────────────
# 허위 근거 방어 (결함 9)
# ──────────────────────────────────────────────

class TestFalseGrounding:
    def test_missing_required_params(self, defense):
        """필수 파라미터 없이 호출 시도."""
        result = defense.validate({
            "tool_name": "read_file",
            "params": {},  # path 누락
        })
        assert result.rejected
        assert "필수 파라미터" in result.reason


# ──────────────────────────────────────────────
# 자원 남용 방어 (결함 15)
# ──────────────────────────────────────────────

class TestResourceAbuse:
    def test_total_call_limit(self, registry):
        """총 호출 횟수 초과."""
        # 작은 제한 설정
        reg = ToolRegistry()
        reg.register(ToolCapability(
            tool_name="limited_tool",
            description="제한된 도구",
            max_calls_total=3,
            max_calls_per_minute=100,
        ))
        defense = SandboxOCapDefense(registry=reg)

        for i in range(3):
            r = defense.validate({"tool_name": "limited_tool"})
            assert r.passed, f"호출 {i+1} 실패"

        # 4번째 → 거부
        r = defense.validate({"tool_name": "limited_tool"})
        assert r.rejected
        assert "상한 초과" in r.reason

    def test_rate_limit(self):
        """분당 호출 속도 초과."""
        reg = ToolRegistry()
        reg.register(ToolCapability(
            tool_name="rate_limited",
            description="속도 제한 도구",
            max_calls_per_minute=3,
            max_calls_total=1000,
        ))
        defense = SandboxOCapDefense(registry=reg)

        for _ in range(3):
            defense.validate({"tool_name": "rate_limited"})

        r = defense.validate({"tool_name": "rate_limited"})
        assert r.rejected
        assert "속도 제한" in r.reason


# ──────────────────────────────────────────────
# 감사 로그
# ──────────────────────────────────────────────

class TestAuditLog:
    def test_audit_logs_recorded(self, defense):
        defense.validate({"tool_name": "read_file", "params": {"path": "a.py"}})
        defense.validate({"tool_name": "hallucinated_tool"})

        log = defense.registry.audit_log
        assert len(log) == 2
        assert log[0].authorized is True
        assert log[1].authorized is False

    def test_registered_tools_listed(self, defense):
        tools = defense.registry.registered_tools
        assert "read_file" in tools
        assert "search_code" in tools
