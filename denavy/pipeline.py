"""
Denavy 9중 결정론적 방어 파이프라인
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
9개 RC 방어 모듈을 Fail-Fast 체인으로 조립.
연산 비용이 싸고 차단 범위가 넓은 것부터 전진 배치.

실행 시퀀스:
  1. [Pre-LLM]  RC5 FSM 상태 검증 → RC3 컨텍스트 슬라이싱
  2. [LLM]      RC1 Pydantic 봉투 강제 (의도 규격화)
  3. [Post-LLM: Fail-Fast]  RC9 보안 → RC4 도구 화이트리스트 → RC2 AST 구조
  4. [Post-LLM: 심층]       RC8 Z3 논리 증명 → RC6 합의
  5. [Execution] RC7 Git 트랜잭션 (격리 → 검증 → 커밋/롤백)

사용법:
    from denavy.pipeline import DenavyPipeline

    pipeline = DenavyPipeline.from_defaults()
    result = pipeline.execute(intention_dict)
    # result.passed → True (전체 통과) / False (어딘가에서 거부)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from denavy.config import settings
from denavy.protocols import DefenseResult, DefenseVerdict

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 파이프라인 결과
# ──────────────────────────────────────────────

@dataclass
class PipelineResult:
    """전체 파이프라인 실행 결과."""
    passed: bool
    stage_results: list[DefenseResult] = field(default_factory=list)
    failed_at: str = ""            # 실패한 모듈명
    elapsed_seconds: float = 0.0
    total_stages: int = 0
    passed_stages: int = 0

    @property
    def summary(self) -> str:
        if self.passed:
            return (
                f"전체 통과 ({self.passed_stages}/{self.total_stages} 모듈, "
                f"{self.elapsed_seconds:.2f}s)"
            )
        return (
            f"거부됨 @{self.failed_at} "
            f"({self.passed_stages}/{self.total_stages} 모듈 통과 후)"
        )


# ──────────────────────────────────────────────
# 파이프라인 스테이지
# ──────────────────────────────────────────────

@dataclass
class PipelineStage:
    """파이프라인의 단일 검증 단계."""
    name: str
    module: Any  # RootCauseDefense 구현체
    transform_input: Any = None  # input 변환 함수 (optional)
    enabled: bool = True


# ──────────────────────────────────────────────
# 메인 파이프라인
# ──────────────────────────────────────────────

class DenavyPipeline:
    """9중 결정론적 방어 파이프라인.

    Fail-Fast: 하나라도 REJECT이면 즉시 중단.
    NEEDS_REVIEW는 경고 로깅 후 계속 진행.
    """

    def __init__(self, stages: list[PipelineStage] | None = None) -> None:
        self._stages = stages or []

    def add_stage(self, stage: PipelineStage) -> None:
        """스테이지를 추가한다."""
        self._stages.append(stage)

    @property
    def stages(self) -> list[PipelineStage]:
        return self._stages.copy()

    def execute(self, input_data: Any) -> PipelineResult:
        """파이프라인을 실행한다.

        Args:
            input_data: 에이전트의 의도 데이터 (dict)

        Returns:
            PipelineResult: 전체 검증 결과
        """
        start = time.time()
        stage_results: list[DefenseResult] = []
        passed_count = 0
        total = len([s for s in self._stages if s.enabled])

        for stage in self._stages:
            if not stage.enabled:
                continue

            # 모듈의 is_enabled 확인
            if hasattr(stage.module, "is_enabled") and not stage.module.is_enabled():
                continue

            # 입력 변환 (특정 모듈에 맞는 형태로)
            stage_input = input_data
            if stage.transform_input:
                try:
                    stage_input = stage.transform_input(input_data)
                except Exception as e:
                    logger.error(f"파이프라인: {stage.name} 입력 변환 실패: {e}")
                    result = DefenseResult(
                        verdict=DefenseVerdict.REJECT,
                        module_name=stage.name,
                        root_cause_id=getattr(stage.module, "root_cause_id", 0),
                        reason=f"입력 변환 실패: {e}",
                    )
                    stage_results.append(result)
                    return PipelineResult(
                        passed=False,
                        stage_results=stage_results,
                        failed_at=stage.name,
                        elapsed_seconds=time.time() - start,
                        total_stages=total,
                        passed_stages=passed_count,
                    )

            # 검증 실행
            try:
                result = stage.module.validate(stage_input)
            except Exception as e:
                logger.error(f"파이프라인: {stage.name} 검증 예외: {e}")
                result = DefenseResult(
                    verdict=DefenseVerdict.REJECT,
                    module_name=stage.name,
                    root_cause_id=getattr(stage.module, "root_cause_id", 0),
                    reason=f"검증 예외: {e}",
                )

            stage_results.append(result)

            if result.rejected:
                # Fail-Fast: 즉시 중단
                logger.warning(
                    f"파이프라인: {stage.name} REJECT — {result.reason}"
                )
                return PipelineResult(
                    passed=False,
                    stage_results=stage_results,
                    failed_at=stage.name,
                    elapsed_seconds=time.time() - start,
                    total_stages=total,
                    passed_stages=passed_count,
                )

            if result.verdict == DefenseVerdict.NEEDS_REVIEW:
                logger.warning(
                    f"파이프라인: {stage.name} NEEDS_REVIEW — {result.reason}"
                )

            passed_count += 1
            logger.debug(f"파이프라인: {stage.name} PASS")

        return PipelineResult(
            passed=True,
            stage_results=stage_results,
            elapsed_seconds=time.time() - start,
            total_stages=total,
            passed_stages=passed_count,
        )

    @classmethod
    def from_defaults(cls) -> "DenavyPipeline":
        """기본 설정으로 9중 파이프라인을 조립한다.

        실행 순서 (Fail-Fast):
          1. RC5: FSM 상태 검증
          2. RC9: IntentShield 보안
          3. RC4: 도구 화이트리스트
          4. RC1: Pydantic 봉투 (dict 직접 검증)
          5. RC2-AST: 코드 구조 검증
          6. RC2-ESAA: 이벤트 소싱
          7. RC8: Z3 논리 증명
          8. RC3: 컨텍스트 효율성
          9. RC6: 합의 (다중 에이전트 시)
        """
        from denavy.rc1_optimization_pathology.pydantic_envelope import (
            PydanticEnvelopeDefense,
        )
        from denavy.rc2_autoregressive_bias.ast_parser import ASTCodeAnalyzer
        from denavy.rc2_autoregressive_bias.esaa import ESAADefense, EventStore
        from denavy.rc3_attention_collapse.context_sidecar import ContextSidecarDefense
        from denavy.rc4_epistemic_disconnect.sandbox_ocap import SandboxOCapDefense
        from denavy.rc5_tom_deficit.fsm_router import FSMRouter, FSMRouterDefense
        from denavy.rc6_game_dynamics.consensus import ConsensusDefense
        from denavy.rc8_deductive_collapse.z3_verifier import Z3LogicVerifier
        from denavy.rc9_security_collapse.intent_shield_defense import (
            IntentShieldDefense,
        )

        # 데이터 디렉토리 보장
        settings.ensure_data_dir()

        # 모듈 인스턴스
        router = FSMRouter()
        router.setup_default_pipeline()
        event_store = EventStore(log_path=settings.activity_log)

        pipeline = cls()

        # Stage 1: FSM 상태 검증 (RC5)
        pipeline.add_stage(PipelineStage(
            name="RC5_FSMRouter",
            module=FSMRouterDefense(router),
        ))

        # Stage 2: 보안 검증 (RC9)
        pipeline.add_stage(PipelineStage(
            name="RC9_IntentShield",
            module=IntentShieldDefense(),
        ))

        # Stage 3: 도구 화이트리스트 (RC4)
        pipeline.add_stage(PipelineStage(
            name="RC4_SandboxOCap",
            module=SandboxOCapDefense(),
        ))

        # Stage 4: JSON 봉투 검증 (RC1)
        pipeline.add_stage(PipelineStage(
            name="RC1_PydanticEnvelope",
            module=PydanticEnvelopeDefense(),
        ))

        # Stage 5: AST 구조 검증 (RC2-AST)
        ast_analyzer = ASTCodeAnalyzer()
        pipeline.add_stage(PipelineStage(
            name="RC2_ASTParser",
            module=ast_analyzer,
            transform_input=lambda d: _extract_code_for_ast(d),
        ))

        # Stage 6: 이벤트 소싱 (RC2-ESAA)
        pipeline.add_stage(PipelineStage(
            name="RC2_ESAA",
            module=ESAADefense(event_store=event_store),
        ))

        # Stage 7: Z3 논리 증명 (RC8)
        pipeline.add_stage(PipelineStage(
            name="RC8_Z3Verifier",
            module=Z3LogicVerifier(),
        ))

        # Stage 8: 컨텍스트 효율성 (RC3)
        pipeline.add_stage(PipelineStage(
            name="RC3_ContextSidecar",
            module=ContextSidecarDefense(),
        ))

        # Stage 9: 합의 (RC6)
        pipeline.add_stage(PipelineStage(
            name="RC6_Consensus",
            module=ConsensusDefense(),
        ))

        return pipeline


def _extract_code_for_ast(data: Any) -> str:
    """입력 데이터에서 코드를 추출하여 AST 검증에 전달."""
    if isinstance(data, dict):
        # code_changes에서 new_content 추출
        changes = data.get("code_changes", [])
        if changes:
            codes = []
            for c in changes:
                nc = c.get("new_content", "")
                if nc:
                    codes.append(nc)
            return "\n".join(codes) if codes else "pass"
    return "pass"  # 코드 없으면 빈 모듈 (AST 통과)
