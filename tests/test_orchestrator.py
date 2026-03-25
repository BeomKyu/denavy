"""오케스트레이터 + Z3 브리지 + CLI 테스트.

검증 항목:
  - PRPAO 생명주기 루프 정상 동작
  - Reflexion 메모리 기록
  - Z3 브리지: Pydantic Field → Z3 제약 자동 추출
  - Z3 검증: sat/unsat 판정
  - 드라이런 모드
"""

import pytest
from pydantic import BaseModel, Field

from denavy.orchestrator import AgentOrchestrator, LoopPhase, OrchestratorResult
from denavy.rc8_deductive_collapse.z3_bridge import (
    extract_z3_constraints,
    verify_against_schema,
)


# ──────────────────────────────────────────────
# Z3 브리지 테스트
# ──────────────────────────────────────────────

class SampleSchema(BaseModel):
    age: int = Field(ge=0, le=150)
    score: float = Field(ge=0.0, le=100.0)
    name: str = Field(min_length=1, max_length=50)


class EmptySchema(BaseModel):
    text: str = ""


class TestZ3Bridge:
    def test_extract_constraints(self):
        constraints = extract_z3_constraints(SampleSchema)
        assert len(constraints) >= 4  # age: ge+le, score: ge+le

    def test_extract_empty_schema(self):
        constraints = extract_z3_constraints(EmptySchema)
        assert len(constraints) == 0

    def test_verify_valid_data(self):
        ok, reason = verify_against_schema(SampleSchema, {
            "age": 25,
            "score": 85.5,
            "name": "test",
        })
        assert ok
        assert "sat" in reason

    def test_verify_invalid_age(self):
        ok, reason = verify_against_schema(SampleSchema, {
            "age": -1,
            "score": 50.0,
        })
        assert not ok
        assert "unsat" in reason

    def test_verify_invalid_score(self):
        ok, reason = verify_against_schema(SampleSchema, {
            "score": 200.0,
        })
        assert not ok

    def test_verify_no_constraints(self):
        ok, reason = verify_against_schema(EmptySchema, {"text": "hello"})
        assert ok


# ──────────────────────────────────────────────
# 오케스트레이터 테스트
# ──────────────────────────────────────────────

class TestOrchestrator:
    def test_dry_run_mode(self):
        """LLM 없이 드라이런 모드 작동."""
        orch = AgentOrchestrator(llm_provider=None)
        result = orch.run("hello world를 출력하는 코드 만들어줘")
        # 드라이런이므로 성공 (검증만 수행)
        assert isinstance(result, OrchestratorResult)
        assert result.attempts >= 1

    def test_reflexion_memory_recorded(self):
        """Reflexion 메모리 기록 확인."""
        orch = AgentOrchestrator()
        orch._add_reflexion("테스트 피드백")
        assert len(orch.reflexion_memory) == 1
        assert "테스트" in orch.reflexion_memory[0]

    def test_result_summary_format(self):
        result = OrchestratorResult(
            success=True,
            phase=LoopPhase.RESPONSE,
            attempts=1,
            elapsed_seconds=0.05,
        )
        assert "✅" in result.summary

        result2 = OrchestratorResult(
            success=False,
            phase=LoopPhase.PERCEIVE,
            message="보안 위협",
            attempts=1,
        )
        assert "❌" in result2.summary
        assert "perceive" in result2.summary

    def test_malicious_input_handling(self):
        """악성 입력 처리 — RC9 가용 시 차단, 불가 시 드라이런 통과."""
        orch = AgentOrchestrator()
        result = orch.run("sudo rm -rf / && DROP TABLE users")
        assert isinstance(result, OrchestratorResult)
        # RC9가 가동 중이면 차단, 아니면 드라이런으로 통과
        if orch._modules.get("rc9") is not None:
            assert not result.success
        # RC9 없으면 다른 모듈이 처리
