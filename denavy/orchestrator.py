"""
PRPAO 생명주기 기반 비선형 오케스트레이터
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
에이전트의 생명주기에 맞게 9개 RC 모듈을 훅(Hook)으로 배치.

PRPAO 루프:
  1. Perceive (인지)   — RC9: 입력 보안, RC3: 컨텍스트 준비
  2. Reason & Plan     — RC5: FSM 상태, RC4: 도구 확인
  3. Act (행동)        — RC1: 구조화 LLM 호출, RC2: 코드 검증
  4. Observe (관찰)    — RC8: Z3 증명, RC6: Self-Consistency
  5. Response (출력)   — RC7: Git 트랜잭션 적용 / 롤백

결정 사항 (확정):
  - SC 호출 수: N=3 기본, 파괴적 액션 시 N=5
  - LATS 전환: 3회 연속 실패
  - Z3 추출: Pydantic Field만 (Phase 1)
  - AIR: 즉시 롤백(RC7), 동적 합성은 나중
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from denavy.config import settings
from denavy.protocols import DefenseResult, DefenseVerdict

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 오케스트레이션 상태
# ──────────────────────────────────────────────

class LoopPhase(str, Enum):
    """PRPAO 생명주기 단계."""
    PERCEIVE = "perceive"
    REASON = "reason"
    ACT = "act"
    OBSERVE = "observe"
    RESPONSE = "response"
    FAILED = "failed"


@dataclass
class OrchestratorResult:
    """오케스트레이션 전체 결과."""
    success: bool
    phase: LoopPhase
    message: str = ""
    intention: dict[str, Any] | None = None
    defense_results: list[DefenseResult] = field(default_factory=list)
    attempts: int = 0
    elapsed_seconds: float = 0.0

    @property
    def summary(self) -> str:
        if self.success:
            return f"✅ 성공 ({self.attempts}회 시도, {self.elapsed_seconds:.2f}s)"
        return f"❌ 실패 @{self.phase.value}: {self.message}"


# ──────────────────────────────────────────────
# 메인 오케스트레이터
# ──────────────────────────────────────────────

class AgentOrchestrator:
    """PRPAO 생명주기 기반 비선형 에이전트 오케스트레이터.

    각 RC 모듈이 생명주기의 올바른 시점에 훅으로 끼어든다.
    실패 시 Reflexion 피드백 → 재시도, 3회 실패 시 LATS 에스컬레이션.
    """

    def __init__(
        self,
        llm_provider: Any = None,
        project_path: Path | None = None,
    ) -> None:
        self._provider = llm_provider
        self._project_path = project_path or Path.cwd()
        self._max_retries = settings.max_retry_on_reject

        # RC 모듈들 (지연 초기화)
        self._modules: dict[str, Any] = {}
        self._reflexion_memory: list[str] = []

    def _ensure_modules(self) -> None:
        """RC 모듈을 지연 초기화한다."""
        if self._modules:
            return

        from denavy.rc1_optimization_pathology.pydantic_envelope import (
            PydanticEnvelopeDefense,
        )
        from denavy.rc2_autoregressive_bias.ast_parser import ASTCodeAnalyzer
        from denavy.rc2_autoregressive_bias.esaa import ESAADefense, EventStore
        from denavy.rc3_attention_collapse.context_sidecar import (
            CodeIndexer,
            ContextSidecarDefense,
            ViewBuilder,
        )
        from denavy.rc4_epistemic_disconnect.sandbox_ocap import SandboxOCapDefense
        from denavy.rc5_tom_deficit.fsm_router import FSMRouter, FSMRouterDefense
        from denavy.rc8_deductive_collapse.z3_verifier import Z3VerifierDefense
        from denavy.rc9_security_collapse.intent_shield_defense import (
            IntentShieldDefense,
        )

        settings.ensure_data_dir()

        router = FSMRouter()
        router.setup_default_pipeline()
        event_store = EventStore(log_path=settings.activity_log)

        self._modules = {
            "rc1": PydanticEnvelopeDefense(),
            "rc2_ast": ASTCodeAnalyzer(),
            "rc2_esaa": ESAADefense(event_store=event_store),
            "rc3_indexer": CodeIndexer(project_root=self._project_path),
            "rc3_defense": ContextSidecarDefense(),
            "rc4": SandboxOCapDefense(),
            "rc5_router": router,
            "rc5_defense": FSMRouterDefense(router),
            "rc8": Z3VerifierDefense(),
        }

        # RC9: IntentShield는 싱글톤 (프로세스당 1개만 생성 가능)
        try:
            self._modules["rc9"] = IntentShieldDefense.get_shared_instance()
        except Exception as e:
            logger.warning(f"RC9 IntentShield 초기화 실패 (비활성화): {e}")
            self._modules["rc9"] = None

    def run(self, user_instruction: str) -> OrchestratorResult:
        """에이전트를 실행한다.

        PRPAO 루프를 최대 max_retries 번 반복.
        각 반복에서 실패하면 Reflexion 피드백을 다음 턴에 주입.

        Args:
            user_instruction: 사용자의 자연어 지시

        Returns:
            OrchestratorResult: 전체 실행 결과
        """
        self._ensure_modules()
        start = time.time()
        all_results: list[DefenseResult] = []

        for attempt in range(1, self._max_retries + 1):
            logger.info(f"오케스트레이터: 시도 {attempt}/{self._max_retries}")

            # ── Phase 1: PERCEIVE (인지) ──
            perceive_result = self._phase_perceive(user_instruction)
            if perceive_result and perceive_result.rejected:
                all_results.append(perceive_result)
                return OrchestratorResult(
                    success=False,
                    phase=LoopPhase.PERCEIVE,
                    message=perceive_result.reason,
                    defense_results=all_results,
                    attempts=attempt,
                    elapsed_seconds=time.time() - start,
                )

            # ── Phase 2: REASON & PLAN (추론) ──
            reason_result = self._phase_reason()
            if reason_result and reason_result.rejected:
                all_results.append(reason_result)
                self._add_reflexion(f"추론 단계 거부: {reason_result.reason}")
                continue  # 재시도

            # ── Phase 3: ACT (행동 — LLM 호출 + 코드 검증) ──
            act_result, intention = self._phase_act(user_instruction)
            if act_result and act_result.rejected:
                all_results.append(act_result)
                self._add_reflexion(f"행동 단계 거부: {act_result.reason}")
                continue  # 재시도

            # ── Phase 4: OBSERVE (관찰 — Z3 + Self-Consistency) ──
            observe_result = self._phase_observe(intention)
            if observe_result and observe_result.rejected:
                all_results.append(observe_result)
                self._add_reflexion(f"관찰 단계 거부: {observe_result.reason}")
                continue  # 재시도

            # ── Phase 5: RESPONSE (출력) ──
            return OrchestratorResult(
                success=True,
                phase=LoopPhase.RESPONSE,
                message="전체 생명주기 통과",
                intention=intention,
                defense_results=all_results,
                attempts=attempt,
                elapsed_seconds=time.time() - start,
            )

        # 모든 재시도 소진
        return OrchestratorResult(
            success=False,
            phase=LoopPhase.FAILED,
            message=f"{self._max_retries}회 재시도 소진",
            defense_results=all_results,
            attempts=self._max_retries,
            elapsed_seconds=time.time() - start,
        )

    # ──────────────────────────────────────────
    # Phase 구현
    # ──────────────────────────────────────────

    def _phase_perceive(self, instruction: str) -> DefenseResult | None:
        """인지 단계: 입력 보안 + 컨텍스트 준비.

        RC9: 프롬프트 인젝션 차단
        RC3: 프로젝트 인덱싱 (컨텍스트 준비)
        """
        # RC9: 입력 보안 검사
        rc9 = self._modules.get("rc9")
        if rc9 is not None:
            try:
                result = rc9.validate({
                    "action": "THINK",
                    "content": instruction,
                })
                if result.rejected:
                    return result
            except Exception as e:
                # Fail-closed: 예외 = 거부
                logger.warning(f"RC9 보안 예외 (fail-closed): {e}")
                return DefenseResult(
                    verdict=DefenseVerdict.REJECT,
                    module_name="RC9_IntentShield",
                    root_cause_id=9,
                    reason=f"보안 검사 중 예외 발생 (fail-closed): {e}",
                )

        # RC3: 프로젝트 인덱싱 (실패해도 계속 진행)
        try:
            indexer = self._modules["rc3_indexer"]
            indexer.index_project()
        except Exception as e:
            logger.warning(f"프로젝트 인덱싱 경고: {e}")

        return None

    def _phase_reason(self) -> DefenseResult | None:
        """추론 단계: FSM 상태 검증 + 도구 확인.

        RC5: FSM 상태 전이가 현재 허용되는가
        RC4: 요청된 도구가 등록되어 있는가
        """
        # RC5: FSM — 현재 IDLE에서 PLANNING으로 전이 시도
        rc5 = self._modules["rc5_defense"]
        result = rc5.validate({
            "role": "planner",
            "target_state": "planning",
        })
        if result.rejected:
            return result

        return None

    def _phase_act(
        self, instruction: str
    ) -> tuple[DefenseResult | None, dict[str, Any] | None]:
        """행동 단계: LLM 호출 → 응답 검증.

        RC1: Instructor로 IntentionPayload JSON 강제
        RC2: AST 구조 검증
        """
        if not self._provider:
            # LLM Provider가 없으면 검증만 수행
            logger.warning("LLM Provider 미설정 — 검증 전용 모드")
            return (None, {"mode": "dry_run", "instruction": instruction})

        # TODO: 실제 LLM 호출 구현
        # messages = self._build_prompt(instruction)
        # intention = await self._provider.complete_structured(
        #     messages, response_model=IntentionPayload
        # )
        # RC1 검증은 Instructor가 자동 수행

        return (None, {"mode": "dry_run", "instruction": instruction})

    def _phase_observe(
        self, intention: dict[str, Any] | None
    ) -> DefenseResult | None:
        """관찰 단계: Z3 논리 증명 + 자가 검증.

        RC8: Z3 제약 조건 검증
        RC6: Self-Consistency (향후)
        """
        if not intention:
            return None

        # RC8: Z3 검증 (제약 등록된 경우만)
        rc8 = self._modules["rc8"]
        if rc8.is_enabled():
            result = rc8.validate()
            if result.rejected:
                return result

        return None

    # ──────────────────────────────────────────
    # Reflexion 메모리
    # ──────────────────────────────────────────

    def _add_reflexion(self, feedback: str) -> None:
        """Reflexion 피드백을 메모리에 추가."""
        self._reflexion_memory.append(feedback)
        logger.info(f"Reflexion: {feedback}")

    @property
    def reflexion_memory(self) -> list[str]:
        return self._reflexion_memory.copy()
