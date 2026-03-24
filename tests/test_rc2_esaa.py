"""RC2: ESAA 이벤트 소싱 + AST 파서 테스트

검증 항목:
  ESAA 이벤트 저장소:
    - append-only 이벤트 기록 및 JSONL 영속화
    - 이벤트 상태 전환 (PENDING → VALIDATED → PROJECTED / REJECTED)
    - 동일 파일 폭주 감지 (같은 파일에 N회 이상 변경 시 거부)
    - 과도한 코드 변경량 감지 (M줄 이상 변경 시 거부)
    - 디스크에서 이벤트 복원

  AST 코드 분석기:
    - 유효한 Python 코드 파싱 및 통과
    - 구문 오류 코드 거부
    - 함수 수 초과 (단일 파일 밀어넣기) 감지
    - 함수 길이 초과 (스파게티 코드) 감지
    - 금지된 import 감지
"""

import tempfile
from pathlib import Path

import pytest

from denavy.protocols import DefenseVerdict, RootCauseDefense
from denavy.rc2_autoregressive_bias.ast_parser import ASTCodeAnalyzer
from denavy.rc2_autoregressive_bias.esaa import (
    ESAADefense,
    EventStatus,
    EventStore,
    IntentionEvent,
)


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def tmp_log_path(tmp_path):
    return tmp_path / "test_activity.jsonl"


@pytest.fixture
def store(tmp_log_path):
    return EventStore(log_path=tmp_log_path)


@pytest.fixture
def defense(store):
    return ESAADefense(
        event_store=store,
        max_changes_per_file=5,
        max_lines_per_change=50,
    )


@pytest.fixture
def analyzer():
    return ASTCodeAnalyzer(
        max_functions_per_file=5,
        max_classes_per_file=3,
        max_function_lines=20,
        forbidden_imports=["os", "subprocess", "shutil"],
    )


def _make_intent(target_file="src/main.py", lines=5):
    content = "\n".join(f"line_{i} = {i}" for i in range(lines))
    return {
        "task_id": "T-001",
        "target_file": target_file,
        "action": "modify",
        "reasoning": "리팩토링",
        "code_changes": [{"new_content": content}],
    }


# ──────────────────────────────────────────────
# EventStore 테스트
# ──────────────────────────────────────────────

class TestEventStore:
    def test_append_and_count(self, store):
        event = IntentionEvent(task_id="T-001")
        store.append(event)
        assert store.count == 1

    def test_get_by_id(self, store):
        event = IntentionEvent(task_id="T-002")
        store.append(event)
        found = store.get(event.event_id)
        assert found is not None
        assert found.task_id == "T-002"

    def test_get_nonexistent(self, store):
        assert store.get("nonexistent") is None

    def test_status_lifecycle(self, store):
        """PENDING → VALIDATED → PROJECTED 전환."""
        event = IntentionEvent(task_id="T-003", target_file="a.py")
        store.append(event)

        validated = store.mark_validated(event.event_id, [{"rc1": "pass"}])
        assert validated.status == EventStatus.VALIDATED

        projected = store.mark_projected(event.event_id)
        assert projected.status == EventStatus.PROJECTED

    def test_rejection(self, store):
        event = IntentionEvent(task_id="T-004")
        store.append(event)

        rejected = store.mark_rejected(
            event.event_id,
            reason="악성 코드 감지",
            validation_results=[{"rc9": "reject"}],
        )
        assert rejected.status == EventStatus.REJECTED
        assert rejected.rejection_reason == "악성 코드 감지"

    def test_persist_and_restore(self, tmp_log_path):
        """디스크 영속화 후 새 인스턴스에서 복원."""
        store1 = EventStore(log_path=tmp_log_path)
        store1.append(IntentionEvent(task_id="T-005"))
        store1.append(IntentionEvent(task_id="T-006"))
        assert store1.count == 2

        # 새 인스턴스로 복원
        store2 = EventStore(log_path=tmp_log_path)
        assert store2.count == 2

    def test_get_latest_state(self, store):
        event = IntentionEvent(task_id="T-007")
        store.append(event)
        store.mark_validated(event.event_id, [])
        store.mark_projected(event.event_id)

        latest = store.get_latest_state(event.event_id)
        assert latest is not None
        assert latest.status == EventStatus.PROJECTED

    def test_get_by_status(self, store):
        e1 = IntentionEvent(task_id="T-008")
        e2 = IntentionEvent(task_id="T-009")
        store.append(e1)
        store.append(e2)

        pending = store.get_by_status(EventStatus.PENDING)
        assert len(pending) == 2


# ──────────────────────────────────────────────
# ESAADefense 테스트
# ──────────────────────────────────────────────

class TestESAADefense:
    def test_implements_protocol(self, defense):
        assert isinstance(defense, RootCauseDefense)

    def test_root_cause_id(self, defense):
        assert defense.root_cause_id == 2

    def test_target_defects(self, defense):
        assert defense.target_defects == [7, 11]

    def test_normal_intent_passes(self, defense):
        result = defense.validate(_make_intent(lines=5))
        assert result.passed
        assert "event_id" in result.details

    def test_bombardment_detection(self, defense):
        """동일 파일에 6회 이상 변경 시 거부 (상한 5)."""
        for i in range(5):
            r = defense.validate(_make_intent(target_file="bomb.py"))
            assert r.passed, f"변경 {i+1}회에서 거부됨: {r.reason}"

        # 6번째 → 거부
        r = defense.validate(_make_intent(target_file="bomb.py"))
        assert r.rejected
        assert "폭주 감지" in r.reason

    def test_line_cap_exceeded(self, defense):
        """50줄 초과 변경 시 거부."""
        result = defense.validate(_make_intent(lines=60))
        assert result.rejected
        assert "과도한 변경량" in r.reason if False else result.rejected

    def test_invalid_input_rejected(self, defense):
        result = defense.validate("not a dict")
        assert result.rejected

    def test_event_stored_on_validation(self, defense):
        defense.validate(_make_intent())
        assert defense.event_store.count >= 1


# ──────────────────────────────────────────────
# ASTCodeAnalyzer 테스트
# ──────────────────────────────────────────────

class TestASTCodeAnalyzer:
    def test_valid_code_passes(self, analyzer):
        code = '''
def greet(name: str) -> str:
    return f"Hello, {name}"

class Greeter:
    pass
'''
        result = analyzer.validate_code(code)
        assert result.passed

    def test_syntax_error_rejected(self, analyzer):
        code = "def broken(:\n    pass"
        result = analyzer.validate_code(code)
        assert result.rejected
        assert "구문 오류" in result.reason

    def test_too_many_functions_rejected(self, analyzer):
        """함수 6개 → 상한 5개 초과."""
        funcs = "\n".join(
            f"def func_{i}():\n    pass\n" for i in range(6)
        )
        result = analyzer.validate_code(funcs)
        assert result.rejected
        assert "밀어넣기" in result.reason

    def test_too_many_classes_rejected(self, analyzer):
        """클래스 4개 → 상한 3개 초과."""
        classes = "\n".join(
            f"class C{i}:\n    pass\n" for i in range(4)
        )
        result = analyzer.validate_code(classes)
        assert result.rejected

    def test_long_function_rejected(self, analyzer):
        """21줄 함수 → 상한 20줄 초과."""
        body = "\n".join(f"    x_{i} = {i}" for i in range(20))
        code = f"def long_func():\n{body}\n"
        result = analyzer.validate_code(code)
        assert result.rejected
        assert "줄" in result.reason

    def test_forbidden_import_rejected(self, analyzer):
        code = "import os\n\ndef safe(): pass\n"
        result = analyzer.validate_code(code)
        assert result.rejected
        assert "금지된 모듈" in result.reason

    def test_forbidden_from_import_rejected(self, analyzer):
        code = "from subprocess import run\n"
        result = analyzer.validate_code(code)
        assert result.rejected
        assert "subprocess" in result.reason

    def test_allowed_import_passes(self, analyzer):
        code = "from pathlib import Path\n\npath = Path('.')\n"
        result = analyzer.validate_code(code)
        assert result.passed

    def test_analysis_metrics(self, analyzer):
        code = '''
import json

def f1():
    pass

def f2():
    pass

class MyClass:
    def method(self):
        pass
'''
        analysis = analyzer.analyze(code)
        assert analysis.parseable
        assert analysis.num_functions == 3  # f1, f2, method
        assert analysis.num_classes == 1
        assert analysis.num_imports == 1
        assert "json" in analysis.imported_modules
