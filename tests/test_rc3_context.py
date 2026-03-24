"""RC3: CQRS 컨텍스트 사이드카 테스트

검증 항목:
  CodeIndexer:
    - Python 파일에서 함수/클래스 심볼 추출
    - import 의존성 수집
    - 이름으로 심볼 검색

  ViewBuilder:
    - 대상 심볼만 선택적으로 뷰 생성
    - 토큰 예산 내 슬라이스 선택
    - 컨텍스트 비율 계산

  ContextSidecarDefense:
    - Protocol 준수
    - 구체화된 뷰 검증 통과
    - 원시 코드 맹목 투입 차단 (토큰 초과)
    - 높은 컨텍스트 비율 경고
"""

import pytest

from denavy.protocols import DefenseVerdict, RootCauseDefense
from denavy.rc3_attention_collapse.context_sidecar import (
    CodeIndexer,
    CodeSlice,
    ContextSidecarDefense,
    MaterializedView,
    ViewBuilder,
)


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

SAMPLE_CODE = '''
import json
from pathlib import Path

def connect_db(url: str) -> None:
    """데이터베이스 연결."""
    print(f"Connecting to {url}")

def query_users(limit: int = 10) -> list:
    """사용자 목록 조회."""
    return [{"id": i} for i in range(limit)]

class UserService:
    """사용자 서비스."""

    def __init__(self, db_url: str):
        self.db_url = db_url

    def get_user(self, user_id: int) -> dict:
        return {"id": user_id}

    def create_user(self, name: str) -> dict:
        return {"name": name}
'''


@pytest.fixture
def project_dir(tmp_path):
    """샘플 프로젝트 디렉토리 생성."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "service.py").write_text(SAMPLE_CODE, encoding="utf-8")
    (src / "utils.py").write_text(
        "def helper():\n    return 42\n\ndef formatter(x):\n    return str(x)\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def indexer(project_dir):
    idx = CodeIndexer(project_root=project_dir)
    idx.index_project()
    return idx


@pytest.fixture
def defense():
    return ContextSidecarDefense(
        max_tokens_per_request=500,
        max_context_ratio=0.8,
    )


# ──────────────────────────────────────────────
# CodeIndexer 테스트
# ──────────────────────────────────────────────

class TestCodeIndexer:
    def test_indexes_files(self, indexer):
        assert len(indexer.indexed_files) >= 2

    def test_extracts_functions(self, indexer):
        slices = indexer.get_slices("src/service.py")
        func_names = [s.symbol_name for s in slices if s.symbol_type == "function"]
        assert "connect_db" in func_names
        assert "query_users" in func_names

    def test_extracts_classes(self, indexer):
        slices = indexer.get_slices("src/service.py")
        class_names = [s.symbol_name for s in slices if s.symbol_type == "class"]
        assert "UserService" in class_names

    def test_captures_imports(self, indexer):
        slices = indexer.get_slices("src/service.py")
        # 함수 슬라이스에 파일의 import가 포함됨
        func_slice = next(s for s in slices if s.symbol_name == "connect_db")
        assert "json" in func_slice.dependencies
        assert "pathlib" in func_slice.dependencies

    def test_find_symbol_by_name(self, indexer):
        results = indexer.find_symbol("UserService")
        assert len(results) == 1
        assert results[0].symbol_type == "class"

    def test_find_symbol_in_specific_file(self, indexer):
        results = indexer.find_symbol("helper", file_path="src/utils.py")
        assert len(results) == 1

    def test_empty_file_returns_empty(self, indexer):
        slices = indexer.get_slices("nonexistent.py")
        assert slices == []

    def test_source_contains_code(self, indexer):
        slices = indexer.get_slices("src/service.py")
        func_slice = next(s for s in slices if s.symbol_name == "connect_db")
        assert "print" in func_slice.source


# ──────────────────────────────────────────────
# ViewBuilder 테스트
# ──────────────────────────────────────────────

class TestViewBuilder:
    def test_build_selective_view(self, indexer):
        builder = ViewBuilder(indexer, max_tokens=8000)
        view = builder.build_view(
            task_id="T-001",
            target_file="src/service.py",
            target_symbols=["connect_db"],
        )
        assert len(view.slices) == 1
        assert view.slices[0].symbol_name == "connect_db"

    def test_build_full_view(self, indexer):
        builder = ViewBuilder(indexer, max_tokens=8000)
        view = builder.build_view(
            task_id="T-002",
            target_file="src/service.py",
        )
        assert len(view.slices) >= 3  # connect_db, query_users, UserService

    def test_token_budget_limits_slices(self, indexer):
        # 매우 작은 토큰 예산
        builder = ViewBuilder(indexer, max_tokens=10)
        view = builder.build_view(
            task_id="T-003",
            target_file="src/service.py",
        )
        # 예산이 극소 → 슬라이스가 거의 포함되지 않음
        assert view.total_tokens_estimate <= 40  # 10 * 4 = 40 chars

    def test_context_ratio_calculated(self, indexer):
        builder = ViewBuilder(indexer, max_tokens=8000)
        view = builder.build_view(
            task_id="T-004",
            target_file="src/service.py",
        )
        assert 0 < view.context_ratio <= 1.0

    def test_total_lines(self, indexer):
        builder = ViewBuilder(indexer, max_tokens=8000)
        view = builder.build_view(
            task_id="T-005",
            target_file="src/service.py",
            target_symbols=["connect_db"],
        )
        assert view.total_lines > 0


# ──────────────────────────────────────────────
# ContextSidecarDefense 테스트
# ──────────────────────────────────────────────

class TestContextSidecarDefense:
    def test_implements_protocol(self, defense):
        assert isinstance(defense, RootCauseDefense)

    def test_root_cause_id(self, defense):
        assert defense.root_cause_id == 3

    def test_target_defects(self, defense):
        assert defense.target_defects == [3, 4, 5]

    def test_efficient_view_passes(self, defense):
        view = MaterializedView(
            task_id="T-001",
            target_file="test.py",
            slices=[CodeSlice(
                file_path="test.py",
                symbol_name="func",
                symbol_type="function",
                start_line=1,
                end_line=5,
                source="def func():\n    pass",
            )],
            total_tokens_estimate=100,
            context_ratio=0.3,
        )
        result = defense.validate(view)
        assert result.passed

    def test_raw_code_dump_blocked(self, defense):
        """원시 코드 맹목 투입: 토큰 초과 시 거부."""
        big_code = "x = 1\n" * 2000  # ~12000 chars → ~3000 tokens > 500
        result = defense.validate({"raw_code": big_code})
        assert result.rejected
        assert "맹목 투입" in result.reason

    def test_raw_string_blocked(self, defense):
        big_str = "a" * 4000  # ~1000 tokens > 500
        result = defense.validate(big_str)
        assert result.rejected

    def test_high_ratio_warns(self, defense):
        """거의 전체 코드를 투입하면 경고."""
        view = MaterializedView(
            task_id="T-002",
            target_file="big.py",
            slices=[],
            total_tokens_estimate=400,  # 예산 내지만
            context_ratio=0.95,         # 비율 초과
        )
        result = defense.validate(view)
        assert result.verdict == DefenseVerdict.NEEDS_REVIEW
        assert "비율" in result.reason

    def test_small_input_passes(self, defense):
        result = defense.validate("짧은 코드")
        assert result.passed
