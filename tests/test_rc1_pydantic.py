"""RC1: Pydantic 봉투 방어 모듈 테스트

검증 항목:
  - 유효한 IntentionPayload 생성 및 통과
  - 게으름 방어: reasoning 미달, code_changes 비어있음
  - 아부 방어: dissenting_considerations 미달
  - 경로 보안: 위험 경로 차단
  - confidence 게이팅: 낮은 확신 + 대규모 변경 거부
  - DELETE 액션 모순 감지
"""

import pytest
from pydantic import ValidationError

from denavy.protocols import DefenseVerdict, RootCauseDefense
from denavy.rc1_optimization_pathology.pydantic_envelope import (
    ActionType,
    CodeChange,
    IntentionPayload,
    PydanticEnvelopeDefense,
)


# ──────────────────────────────────────────────
# 유틸리티: 유효한 테스트 데이터 생성
# ──────────────────────────────────────────────

def _make_valid_payload(**overrides) -> dict:
    """유효한 IntentionPayload dict를 생성한다."""
    base = {
        "task_id": "TASK-001",
        "target_file": "src/main.py",
        "action": "modify",
        "reasoning": "기존 함수의 반환 타입을 Optional로 수정하여 None 케이스 처리",
        "code_changes": [
            {
                "target_line_start": 10,
                "target_line_end": 15,
                "original_content": "def foo() -> str:",
                "new_content": "def foo() -> str | None:",
                "rationale": "None 반환 가능성을 타입 시스템에 반영",
            }
        ],
        "confidence_score": 0.85,
        "dissenting_considerations": "이 변경으로 인해 호출부에서 None 체크가 필요할 수 있음",
    }
    base.update(overrides)
    return base


# ──────────────────────────────────────────────
# Protocol 준수 테스트
# ──────────────────────────────────────────────

class TestProtocolCompliance:
    """RC1 방어 모듈이 RootCauseDefense Protocol을 준수하는지 확인."""

    def test_implements_protocol(self):
        defense = PydanticEnvelopeDefense()
        assert isinstance(defense, RootCauseDefense)

    def test_root_cause_id(self):
        defense = PydanticEnvelopeDefense()
        assert defense.root_cause_id == 1

    def test_target_defects(self):
        defense = PydanticEnvelopeDefense()
        assert defense.target_defects == [1, 2]

    def test_is_enabled(self):
        defense = PydanticEnvelopeDefense()
        assert defense.is_enabled() is True


# ──────────────────────────────────────────────
# 유효한 페이로드 테스트
# ──────────────────────────────────────────────

class TestValidPayload:
    """유효한 의도 봉투가 정상 통과하는지 확인."""

    def test_valid_dict_passes(self):
        defense = PydanticEnvelopeDefense()
        result = defense.validate(_make_valid_payload())
        assert result.passed
        assert result.verdict == DefenseVerdict.PASS

    def test_valid_model_passes(self):
        defense = PydanticEnvelopeDefense()
        payload = IntentionPayload.model_validate(_make_valid_payload())
        result = defense.validate(payload)
        assert result.passed

    def test_valid_json_string_passes(self):
        defense = PydanticEnvelopeDefense()
        payload = IntentionPayload.model_validate(_make_valid_payload())
        json_str = payload.model_dump_json()
        result = defense.validate(json_str)
        assert result.passed

    def test_create_action_valid(self):
        data = _make_valid_payload(action="create")
        payload = IntentionPayload.model_validate(data)
        assert payload.action == ActionType.CREATE

    def test_delete_action_valid(self):
        """DELETE 액션에서 new_content가 비어있으면 유효."""
        data = _make_valid_payload(
            action="delete",
            code_changes=[{
                "target_line_start": 1,
                "target_line_end": 5,
                "original_content": "def old():\n    pass",
                "new_content": "",
                "rationale": "사용되지 않는 레거시 함수 제거",
            }]
        )
        payload = IntentionPayload.model_validate(data)
        assert payload.action == ActionType.DELETE


# ──────────────────────────────────────────────
# 게으름(결함 1) 방어 테스트
# ──────────────────────────────────────────────

class TestDefect1LazynessDefense:
    """결함 1 — 극단적 게으름 방어 검증."""

    def test_short_reasoning_rejected(self):
        """reasoning이 20자 미만이면 거부."""
        data = _make_valid_payload(reasoning="짧음")
        defense = PydanticEnvelopeDefense()
        result = defense.validate(data)
        assert result.rejected

    def test_empty_code_changes_rejected(self):
        """code_changes가 비어있으면 거부."""
        data = _make_valid_payload(code_changes=[])
        defense = PydanticEnvelopeDefense()
        result = defense.validate(data)
        assert result.rejected

    def test_missing_task_id_rejected(self):
        """task_id 누락 시 거부."""
        data = _make_valid_payload()
        del data["task_id"]
        defense = PydanticEnvelopeDefense()
        result = defense.validate(data)
        assert result.rejected

    def test_short_rationale_rejected(self):
        """개별 변경의 rationale이 10자 미만이면 거부."""
        data = _make_valid_payload(
            code_changes=[{
                "target_line_start": 1,
                "target_line_end": 1,
                "original_content": "x = 1",
                "new_content": "x = 2",
                "rationale": "수정",  # 10자 미만
            }]
        )
        defense = PydanticEnvelopeDefense()
        result = defense.validate(data)
        assert result.rejected


# ──────────────────────────────────────────────
# 아부(결함 2) 방어 테스트
# ──────────────────────────────────────────────

class TestDefect2SycophancyDefense:
    """결함 2 — 무지성 아부 방어 검증."""

    def test_short_dissenting_rejected(self):
        """dissenting_considerations가 10자 미만이면 거부."""
        data = _make_valid_payload(dissenting_considerations="없음")
        defense = PydanticEnvelopeDefense()
        result = defense.validate(data)
        assert result.rejected

    def test_confidence_out_of_range_rejected(self):
        """confidence_score가 0~1 범위 밖이면 거부."""
        data = _make_valid_payload(confidence_score=1.5)
        defense = PydanticEnvelopeDefense()
        result = defense.validate(data)
        assert result.rejected

    def test_low_confidence_high_changes_rejected(self):
        """낮은 확신(< 0.3) + 6개 이상 변경 시 거부."""
        changes = [
            {
                "target_line_start": i,
                "target_line_end": i,
                "original_content": f"line_{i}",
                "new_content": f"new_line_{i}",
                "rationale": f"변경 {i}번: 리팩토링 대상 함수 수정",
            }
            for i in range(1, 7)  # 6개 변경
        ]
        data = _make_valid_payload(
            confidence_score=0.2,
            code_changes=changes,
        )
        defense = PydanticEnvelopeDefense()
        result = defense.validate(data)
        assert result.rejected


# ──────────────────────────────────────────────
# 경로 보안 테스트
# ──────────────────────────────────────────────

class TestPathSecurity:
    """위험한 파일 경로 접근 차단 검증."""

    def test_path_traversal_rejected(self):
        data = _make_valid_payload(target_file="../../etc/passwd")
        defense = PydanticEnvelopeDefense()
        result = defense.validate(data)
        assert result.rejected

    def test_system_path_linux_rejected(self):
        data = _make_valid_payload(target_file="/etc/shadow")
        defense = PydanticEnvelopeDefense()
        result = defense.validate(data)
        assert result.rejected

    def test_system_path_windows_rejected(self):
        data = _make_valid_payload(target_file="C:\\Windows\\System32\\cmd.exe")
        defense = PydanticEnvelopeDefense()
        result = defense.validate(data)
        assert result.rejected


# ──────────────────────────────────────────────
# 모순 감지 테스트
# ──────────────────────────────────────────────

class TestContradictionDetection:
    """의도 내 논리적 모순 감지 검증."""

    def test_delete_with_new_content_rejected(self):
        """DELETE 액션에서 new_content가 비어있지 않으면 거부."""
        data = _make_valid_payload(
            action="delete",
            code_changes=[{
                "target_line_start": 1,
                "target_line_end": 5,
                "original_content": "def old():\n    pass",
                "new_content": "def new():\n    return 42",  # 모순!
                "rationale": "삭제한다고 했지만 새 코드를 넣으려 한다",
            }]
        )
        defense = PydanticEnvelopeDefense()
        result = defense.validate(data)
        assert result.rejected

    def test_line_range_inverted_rejected(self):
        """target_line_end < target_line_start이면 거부."""
        data = _make_valid_payload(
            code_changes=[{
                "target_line_start": 10,
                "target_line_end": 5,  # 역전!
                "original_content": "x = 1",
                "new_content": "x = 2",
                "rationale": "변수값 수정을 위한 라인 범위 지정",
            }]
        )
        defense = PydanticEnvelopeDefense()
        result = defense.validate(data)
        assert result.rejected


# ──────────────────────────────────────────────
# 잘못된 입력 타입 테스트
# ──────────────────────────────────────────────

class TestInvalidInputTypes:
    """지원하지 않는 입력 타입에 대한 거부 확인."""

    def test_integer_rejected(self):
        defense = PydanticEnvelopeDefense()
        result = defense.validate(42)
        assert result.rejected

    def test_none_rejected(self):
        defense = PydanticEnvelopeDefense()
        result = defense.validate(None)
        assert result.rejected

    def test_list_rejected(self):
        defense = PydanticEnvelopeDefense()
        result = defense.validate([1, 2, 3])
        assert result.rejected
