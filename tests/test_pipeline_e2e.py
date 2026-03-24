"""Pipeline E2E 통합 테스트

불량 LLM 응답을 주입하여 정확한 방어 단계에서 REJECT이 발생하는지 검증.

테스트 시나리오:
  1. 정상 의도 → 전체 통과
  2. 게으른 응답 (짧은 reasoning) → RC1에서 거부
  3. 환각 도구 호출 → RC4에서 거부
  4. 스파게티 코드 (함수 수 폭주) → RC2에서 거부
  5. 악성 코드 (셸 인젝션) → RC9에서 거부
  6. 동일 파일 폭주 → RC2 ESAA에서 거부
  7. Fail-Fast 검증 (조기 중단 확인)
  8. 비활성 스테이지 건너뛰기
"""

import time

import pytest

from denavy.pipeline import DenavyPipeline, PipelineResult, PipelineStage
from denavy.protocols import DefenseResult, DefenseVerdict


# ──────────────────────────────────────────────
# 모크 모듈
# ──────────────────────────────────────────────

class MockPassModule:
    """항상 통과하는 모크 모듈."""
    root_cause_id = 99
    target_defects = [99]

    def is_enabled(self):
        return True

    def validate(self, input_data):
        return DefenseResult(
            verdict=DefenseVerdict.PASS,
            module_name="MockPass",
            root_cause_id=99,
            reason="모크 통과",
        )


class MockRejectModule:
    """항상 거부하는 모크 모듈."""
    root_cause_id = 98
    target_defects = [98]

    def is_enabled(self):
        return True

    def validate(self, input_data):
        return DefenseResult(
            verdict=DefenseVerdict.REJECT,
            module_name="MockReject",
            root_cause_id=98,
            reason="모크 거부",
        )


class MockDisabledModule:
    """비활성화된 모크."""
    root_cause_id = 97
    target_defects = [97]

    def is_enabled(self):
        return False

    def validate(self, input_data):
        raise AssertionError("비활성 모듈이 호출됨!")


class MockExceptionModule:
    """예외를 던지는 모듈."""
    root_cause_id = 96
    target_defects = [96]

    def is_enabled(self):
        return True

    def validate(self, input_data):
        raise RuntimeError("의도적 폭발!")


# ──────────────────────────────────────────────
# 파이프라인 기본 동작
# ──────────────────────────────────────────────

class TestPipelineBasics:
    def test_empty_pipeline_passes(self):
        pipeline = DenavyPipeline()
        result = pipeline.execute({"test": True})
        assert result.passed

    def test_all_pass_pipeline(self):
        pipeline = DenavyPipeline([
            PipelineStage(name="A", module=MockPassModule()),
            PipelineStage(name="B", module=MockPassModule()),
            PipelineStage(name="C", module=MockPassModule()),
        ])
        result = pipeline.execute({})
        assert result.passed
        assert result.passed_stages == 3
        assert result.total_stages == 3

    def test_fail_fast(self):
        """첫 번째 REJECT에서 즉시 중단."""
        pipeline = DenavyPipeline([
            PipelineStage(name="Pass1", module=MockPassModule()),
            PipelineStage(name="Reject", module=MockRejectModule()),
            PipelineStage(name="NeverReached", module=MockPassModule()),
        ])
        result = pipeline.execute({})
        assert not result.passed
        assert result.failed_at == "Reject"
        assert result.passed_stages == 1
        assert len(result.stage_results) == 2  # Pass1 + Reject

    def test_disabled_stage_skipped(self):
        pipeline = DenavyPipeline([
            PipelineStage(name="Active", module=MockPassModule()),
            PipelineStage(name="Disabled", module=MockDisabledModule()),
            PipelineStage(name="Active2", module=MockPassModule()),
        ])
        result = pipeline.execute({})
        assert result.passed

    def test_exception_treated_as_reject(self):
        """모듈 예외 → REJECT 처리."""
        pipeline = DenavyPipeline([
            PipelineStage(name="Bomb", module=MockExceptionModule()),
        ])
        result = pipeline.execute({})
        assert not result.passed
        assert "예외" in result.stage_results[0].reason

    def test_elapsed_time_tracked(self):
        pipeline = DenavyPipeline([
            PipelineStage(name="A", module=MockPassModule()),
        ])
        result = pipeline.execute({})
        assert result.elapsed_seconds >= 0

    def test_summary_on_pass(self):
        pipeline = DenavyPipeline([
            PipelineStage(name="A", module=MockPassModule()),
        ])
        result = pipeline.execute({})
        assert "전체 통과" in result.summary

    def test_summary_on_reject(self):
        pipeline = DenavyPipeline([
            PipelineStage(name="Blocker", module=MockRejectModule()),
        ])
        result = pipeline.execute({})
        assert "거부됨" in result.summary
        assert "Blocker" in result.summary


# ──────────────────────────────────────────────
# 실제 RC 모듈 개별 검증 (E2E)
# ──────────────────────────────────────────────

class TestRC1Integration:
    """RC1: 게으른/아부성 응답 차단."""

    def test_lazy_reasoning_rejected(self):
        from denavy.rc1_optimization_pathology.pydantic_envelope import (
            PydanticEnvelopeDefense,
        )
        pipeline = DenavyPipeline([
            PipelineStage(name="RC1", module=PydanticEnvelopeDefense()),
        ])
        # reasoning이 너무 짧음
        result = pipeline.execute({
            "task_id": "T-001",
            "target_file": "src/main.py",
            "action": "modify",
            "reasoning": "ok",  # 게으름!
            "code_changes": [{"new_content": "x = 1"}],
            "confidence_score": 0.8,
            "dissenting_considerations": "별 문제 없음",
        })
        assert not result.passed
        assert result.failed_at == "RC1"


class TestRC2Integration:
    """RC2: 코드 구조 검증."""

    def test_spaghetti_code_rejected(self):
        from denavy.rc2_autoregressive_bias.ast_parser import ASTCodeAnalyzer
        pipeline = DenavyPipeline([
            PipelineStage(
                name="RC2_AST",
                module=ASTCodeAnalyzer(max_functions_per_file=5),
            ),
        ])
        # 함수 10개 밀어넣기
        code = "\n".join(f"def func_{i}():\n    pass\n" for i in range(10))
        result = pipeline.execute(code)
        assert not result.passed

    def test_bombardment_rejected(self, tmp_path):
        from denavy.rc2_autoregressive_bias.esaa import ESAADefense, EventStore
        store = EventStore(log_path=tmp_path / "test.jsonl")
        defense = ESAADefense(event_store=store, max_changes_per_file=3)
        pipeline = DenavyPipeline([
            PipelineStage(name="RC2_ESAA", module=defense),
        ])
        intent = {
            "task_id": "T-001",
            "target_file": "bomb.py",
            "action": "modify",
            "code_changes": [{"new_content": "x = 1"}],
        }
        for _ in range(3):
            pipeline.execute(intent)

        # 4번째 → 폭주 감지
        result = pipeline.execute(intent)
        assert not result.passed


class TestRC4Integration:
    """RC4: 환각 도구 호출 차단."""

    def test_hallucinated_tool_rejected(self):
        from denavy.rc4_epistemic_disconnect.sandbox_ocap import (
            SandboxOCapDefense,
            ToolCapability,
            ToolRegistry,
        )
        reg = ToolRegistry()
        reg.register(ToolCapability(tool_name="read_file", description="파일 읽기"))
        pipeline = DenavyPipeline([
            PipelineStage(name="RC4", module=SandboxOCapDefense(registry=reg)),
        ])
        result = pipeline.execute({
            "tool_name": "run_nuclear_launch",  # 환각!
        })
        assert not result.passed
        assert "환각" in result.stage_results[0].reason


class TestRC5Integration:
    """RC5: 역할 침범 차단."""

    def test_role_invasion_rejected(self):
        from denavy.rc5_tom_deficit.fsm_router import FSMRouter, FSMRouterDefense
        r = FSMRouter()
        r.setup_default_pipeline()
        pipeline = DenavyPipeline([
            PipelineStage(name="RC5", module=FSMRouterDefense(r)),
        ])
        result = pipeline.execute({
            "role": "coder",
            "target_state": "planning",
        })
        assert not result.passed
        assert "역할 침범" in result.stage_results[0].reason


class TestRC6Integration:
    """RC6: 기권 차단."""

    def test_incomplete_consensus_rejected(self):
        from denavy.rc6_game_dynamics.consensus import ConsensusDefense
        pipeline = DenavyPipeline([
            PipelineStage(name="RC6", module=ConsensusDefense()),
        ])
        # 아무도 투표하지 않았으므로 합의 불완전
        result = pipeline.execute(None)
        assert not result.passed


class TestMultiStageE2E:
    """다중 모듈 체인 E2E."""

    def test_normal_passes_ast_and_esaa(self, tmp_path):
        from denavy.rc2_autoregressive_bias.ast_parser import ASTCodeAnalyzer
        from denavy.rc2_autoregressive_bias.esaa import ESAADefense, EventStore

        store = EventStore(log_path=tmp_path / "e2e.jsonl")
        pipeline = DenavyPipeline([
            PipelineStage(
                name="RC2_AST",
                module=ASTCodeAnalyzer(),
                transform_input=lambda d: d.get("code", "pass"),
            ),
            PipelineStage(name="RC2_ESAA", module=ESAADefense(event_store=store)),
        ])
        result = pipeline.execute({
            "task_id": "T-001",
            "target_file": "clean.py",
            "action": "create",
            "code": "def hello():\n    return 'world'\n",
            "code_changes": [{"new_content": "def hello():\n    return 'world'\n"}],
        })
        assert result.passed
        assert result.passed_stages == 2

    def test_invalid_code_fails_at_ast(self, tmp_path):
        from denavy.rc2_autoregressive_bias.ast_parser import ASTCodeAnalyzer
        from denavy.rc2_autoregressive_bias.esaa import ESAADefense, EventStore

        store = EventStore(log_path=tmp_path / "e2e2.jsonl")
        pipeline = DenavyPipeline([
            PipelineStage(
                name="RC2_AST",
                module=ASTCodeAnalyzer(),
                transform_input=lambda d: d.get("code", "pass"),
            ),
            PipelineStage(name="RC2_ESAA", module=ESAADefense(event_store=store)),
        ])
        result = pipeline.execute({
            "task_id": "T-002",
            "target_file": "broken.py",
            "code": "def broken(:\n    pass",
            "code_changes": [{"new_content": "def broken(:\n    pass"}],
        })
        assert not result.passed
        assert result.failed_at == "RC2_AST"
        # ESAA는 실행되지 않음 (Fail-Fast)
        assert result.passed_stages == 0
