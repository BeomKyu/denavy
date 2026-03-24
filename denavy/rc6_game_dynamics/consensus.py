"""
RC6: CONSENSAGENT — 결정론적 합의 프로토콜
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
근본 원인 6 — 게임 이론적 역학 오류

억압 결함:
  결함 18 — 사회적 태만: 다중 에이전트 중 일부가 실질적 판단 없이 통과
  결함 20 — 집단사고: 에이전트들이 무비판적으로 동조

핵심 원리:
  여러 에이전트(또는 여러 검증 모듈)의 판단을 합의(Consensus)로 통합.
  - 각 투표자(Voter)는 독립적으로 판단을 제출
  - 만장일치 또는 다수결로만 통과
  - "기권" 또는 "근거 없는 통과"를 허용하지 않음
  - 모든 투표자가 구체적 근거(reasoning)를 제시해야 유효

엔터프라이즈의 무거운 PBFT/Raft를 버리고,
단순한 투표 + 근거 강제 + 이중 부정(Devil's Advocate) 방식으로 구현.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from denavy.protocols import DefenseResult, DefenseVerdict, RootCauseDefense

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 투표 데이터 모델
# ──────────────────────────────────────────────

class VoteDecision(str, Enum):
    """투표 결정."""
    APPROVE = "approve"
    REJECT = "reject"
    ABSTAIN = "abstain"


@dataclass
class Vote:
    """단일 투표."""
    voter_id: str
    decision: VoteDecision
    reasoning: str
    confidence: float = 0.0  # 0.0 ~ 1.0
    timestamp: float = field(default_factory=time.time)

    @property
    def has_substance(self) -> bool:
        """투표에 실질적 근거가 있는가 (태만 방어)."""
        return len(self.reasoning.strip()) >= 20

    @property
    def is_valid(self) -> bool:
        """유효한 투표인가."""
        if self.decision == VoteDecision.ABSTAIN:
            return False
        return self.has_substance


@dataclass
class ConsensusResult:
    """합의 결과."""
    passed: bool
    votes: list[Vote]
    summary: str
    approval_rate: float = 0.0
    invalid_votes: list[str] = field(default_factory=list)  # voter_ids


# ──────────────────────────────────────────────
# 합의 프로토콜
# ──────────────────────────────────────────────

class ConsensusProtocol:
    """결정론적 합의 프로토콜.

    N명의 투표자가 독립적으로 판단을 제출.
    - 기권(ABSTAIN)은 무효 처리 (사회적 태만 방어)
    - 근거(reasoning) 20자 미만은 무효 (근거 없는 동조 방어)
    - 만장일치 또는 다수결 모드 선택 가능
    """

    def __init__(
        self,
        required_voters: list[str],
        mode: str = "majority",  # "unanimity" | "majority"
        min_reasoning_length: int = 20,
    ) -> None:
        """
        Args:
            required_voters: 필수 투표자 ID 목록
            mode: "unanimity" (만장일치) 또는 "majority" (다수결)
            min_reasoning_length: 근거 최소 길이
        """
        self._required_voters = set(required_voters)
        self._mode = mode
        self._min_reasoning = min_reasoning_length
        self._votes: dict[str, Vote] = {}

    @property
    def required_voters(self) -> set[str]:
        return self._required_voters.copy()

    @property
    def submitted_voters(self) -> set[str]:
        return set(self._votes.keys())

    @property
    def missing_voters(self) -> set[str]:
        return self._required_voters - set(self._votes.keys())

    def submit_vote(self, vote: Vote) -> tuple[bool, str]:
        """투표를 제출한다.

        Args:
            vote: 제출할 투표

        Returns:
            (수락 여부, 사유)
        """
        # 필수 투표자 확인
        if vote.voter_id not in self._required_voters:
            return (False, f"미등록 투표자: {vote.voter_id}")

        # 중복 투표 방지
        if vote.voter_id in self._votes:
            return (False, f"중복 투표: {vote.voter_id}")

        # 기권 불허
        if vote.decision == VoteDecision.ABSTAIN:
            return (
                False,
                f"기권 불허: {vote.voter_id}는 명확한 APPROVE/REJECT를 제출해야 함",
            )

        # 근거 최소 길이 확인
        if len(vote.reasoning.strip()) < self._min_reasoning:
            return (
                False,
                f"근거 부족: {vote.voter_id}의 reasoning이 "
                f"{len(vote.reasoning.strip())}자 "
                f"(최소 {self._min_reasoning}자)",
            )

        self._votes[vote.voter_id] = vote
        return (True, f"투표 수락: {vote.voter_id} → {vote.decision.value}")

    def tally(self) -> ConsensusResult:
        """투표를 집계한다.

        Returns:
            ConsensusResult: 합의 결과
        """
        # 모든 필수 투표자가 투표했는가
        missing = self.missing_voters
        if missing:
            return ConsensusResult(
                passed=False,
                votes=list(self._votes.values()),
                summary=f"미투표자 {len(missing)}명: {', '.join(missing)}",
                invalid_votes=list(missing),
            )

        all_votes = list(self._votes.values())
        valid_votes = [v for v in all_votes if v.is_valid]
        invalid_ids = [
            v.voter_id for v in all_votes if not v.is_valid
        ]

        if not valid_votes:
            return ConsensusResult(
                passed=False,
                votes=all_votes,
                summary="유효한 투표 없음",
                invalid_votes=invalid_ids,
            )

        approvals = sum(
            1 for v in valid_votes if v.decision == VoteDecision.APPROVE
        )
        total_valid = len(valid_votes)
        rate = approvals / total_valid if total_valid > 0 else 0.0

        if self._mode == "unanimity":
            passed = approvals == total_valid
            summary = (
                f"만장일치 {'통과' if passed else '실패'}: "
                f"{approvals}/{total_valid} 승인"
            )
        else:
            passed = approvals > total_valid / 2
            summary = (
                f"다수결 {'통과' if passed else '실패'}: "
                f"{approvals}/{total_valid} 승인 ({rate:.0%})"
            )

        return ConsensusResult(
            passed=passed,
            votes=all_votes,
            summary=summary,
            approval_rate=round(rate, 3),
            invalid_votes=invalid_ids,
        )

    def reset(self) -> None:
        """투표를 초기화한다."""
        self._votes.clear()


# ──────────────────────────────────────────────
# RC6 방어 모듈
# ──────────────────────────────────────────────

class ConsensusDefense:
    """RC6: CONSENSAGENT 합의 방어 모듈.

    다중 검증 모듈의 판단을 합의 프로토콜로 통합한다.
    이 모듈은 RootCauseDefense Protocol을 구현한다.

    validate()는 합의 결과를 검증:
      1. 모든 필수 투표자가 참여했는가 (태만 방어)
      2. 근거가 충분한가 (집단사고 방어)
      3. 합의에 도달했는가
    """

    def __init__(
        self,
        protocol: ConsensusProtocol | None = None,
        required_voters: list[str] | None = None,
        mode: str = "majority",
    ) -> None:
        if protocol:
            self._protocol = protocol
        else:
            voters = required_voters or ["rc1", "rc8", "rc9"]
            self._protocol = ConsensusProtocol(
                required_voters=voters,
                mode=mode,
            )

    @property
    def root_cause_id(self) -> int:
        return 6

    @property
    def target_defects(self) -> list[int]:
        return [18, 20]

    def is_enabled(self) -> bool:
        return True

    @property
    def protocol(self) -> ConsensusProtocol:
        return self._protocol

    def validate(self, input_data: Any = None) -> DefenseResult:
        """합의 결과를 검증한다.

        Args:
            input_data: None (자동 집계) 또는 ConsensusResult 직접 전달

        Returns:
            DefenseResult: 합의 결과에 따른 검증 결과
        """
        if isinstance(input_data, ConsensusResult):
            result = input_data
        else:
            result = self._protocol.tally()

        if result.invalid_votes:
            return DefenseResult(
                verdict=DefenseVerdict.REJECT,
                module_name="RC6_Consensus",
                root_cause_id=6,
                reason=(
                    f"합의 불완전: 무효 투표자 "
                    f"{len(result.invalid_votes)}명 — {result.summary}"
                ),
                details={
                    "invalid_voters": result.invalid_votes,
                    "approval_rate": result.approval_rate,
                },
            )

        if not result.passed:
            return DefenseResult(
                verdict=DefenseVerdict.REJECT,
                module_name="RC6_Consensus",
                root_cause_id=6,
                reason=f"합의 실패: {result.summary}",
                details={"approval_rate": result.approval_rate},
            )

        return DefenseResult(
            verdict=DefenseVerdict.PASS,
            module_name="RC6_Consensus",
            root_cause_id=6,
            reason=f"합의 통과: {result.summary}",
            details={"approval_rate": result.approval_rate},
        )
