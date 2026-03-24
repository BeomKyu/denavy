"""RC6: CONSENSAGENT 합의 프로토콜 테스트

검증 항목:
  - Protocol 준수
  - 정상 합의 (만장일치/다수결 통과)
  - 기권 불허 (사회적 태만 방어)
  - 근거 부족 거부 (집단사고 방어)
  - 미투표자 감지
  - 중복 투표 방지
  - 미등록 투표자 거부
"""

import pytest

from denavy.protocols import DefenseVerdict, RootCauseDefense
from denavy.rc6_game_dynamics.consensus import (
    ConsensusDefense,
    ConsensusProtocol,
    Vote,
    VoteDecision,
)


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

def _vote(voter_id: str, decision: str, reasoning: str = "", conf: float = 0.8):
    return Vote(
        voter_id=voter_id,
        decision=VoteDecision(decision),
        reasoning=reasoning or f"{voter_id}의 충분한 근거를 포함한 판단 결과입니다 ({decision})",
        confidence=conf,
    )


@pytest.fixture
def protocol():
    return ConsensusProtocol(
        required_voters=["rc1", "rc8", "rc9"],
        mode="majority",
    )


@pytest.fixture
def unanimity_protocol():
    return ConsensusProtocol(
        required_voters=["rc1", "rc8", "rc9"],
        mode="unanimity",
    )


@pytest.fixture
def defense(protocol):
    return ConsensusDefense(protocol=protocol)


# ──────────────────────────────────────────────
# Protocol 준수
# ──────────────────────────────────────────────

class TestProtocolCompliance:
    def test_implements_protocol(self, defense):
        assert isinstance(defense, RootCauseDefense)

    def test_root_cause_id(self, defense):
        assert defense.root_cause_id == 6

    def test_target_defects(self, defense):
        assert defense.target_defects == [18, 20]


# ──────────────────────────────────────────────
# 정상 합의
# ──────────────────────────────────────────────

class TestNormalConsensus:
    def test_majority_passes(self, protocol):
        """2/3 승인 → 다수결 통과."""
        protocol.submit_vote(_vote("rc1", "approve"))
        protocol.submit_vote(_vote("rc8", "approve"))
        protocol.submit_vote(_vote("rc9", "reject"))
        result = protocol.tally()
        assert result.passed
        assert result.approval_rate > 0.5

    def test_majority_fails(self, protocol):
        """1/3 승인 → 다수결 실패."""
        protocol.submit_vote(_vote("rc1", "approve"))
        protocol.submit_vote(_vote("rc8", "reject"))
        protocol.submit_vote(_vote("rc9", "reject"))
        result = protocol.tally()
        assert not result.passed

    def test_unanimity_passes(self, unanimity_protocol):
        """3/3 승인 → 만장일치 통과."""
        unanimity_protocol.submit_vote(_vote("rc1", "approve"))
        unanimity_protocol.submit_vote(_vote("rc8", "approve"))
        unanimity_protocol.submit_vote(_vote("rc9", "approve"))
        result = unanimity_protocol.tally()
        assert result.passed
        assert result.approval_rate == 1.0

    def test_unanimity_fails_with_one_reject(self, unanimity_protocol):
        """2/3 승인 → 만장일치 실패."""
        unanimity_protocol.submit_vote(_vote("rc1", "approve"))
        unanimity_protocol.submit_vote(_vote("rc8", "approve"))
        unanimity_protocol.submit_vote(_vote("rc9", "reject"))
        result = unanimity_protocol.tally()
        assert not result.passed


# ──────────────────────────────────────────────
# 사회적 태만 방어 (결함 18)
# ──────────────────────────────────────────────

class TestSocialLoafing:
    def test_abstain_rejected(self, protocol):
        """기권은 허용하지 않음."""
        ok, reason = protocol.submit_vote(
            Vote(voter_id="rc1", decision=VoteDecision.ABSTAIN, reasoning="모르겠음")
        )
        assert not ok
        assert "기권 불허" in reason

    def test_missing_voters_detected(self, protocol):
        """일부만 투표하면 합의 실패."""
        protocol.submit_vote(_vote("rc1", "approve"))
        # rc8, rc9 미투표
        result = protocol.tally()
        assert not result.passed
        assert "미투표자" in result.summary

    def test_defense_rejects_incomplete(self, defense):
        defense.protocol.submit_vote(_vote("rc1", "approve"))
        result = defense.validate()
        assert result.rejected
        assert "불완전" in result.reason


# ──────────────────────────────────────────────
# 집단사고 방어 (결함 20)
# ──────────────────────────────────────────────

class TestGroupthink:
    def test_short_reasoning_rejected(self, protocol):
        """근거가 너무 짧으면 거부."""
        ok, reason = protocol.submit_vote(
            Vote(voter_id="rc1", decision=VoteDecision.APPROVE, reasoning="ok")
        )
        assert not ok
        assert "근거 부족" in reason

    def test_adequate_reasoning_accepted(self, protocol):
        ok, _ = protocol.submit_vote(
            Vote(
                voter_id="rc1",
                decision=VoteDecision.APPROVE,
                reasoning="이 코드 변경은 기존 아키텍처 패턴을 정확하게 따르고 있습니다",
            )
        )
        assert ok


# ──────────────────────────────────────────────
# 기타 검증
# ──────────────────────────────────────────────

class TestEdgeCases:
    def test_duplicate_vote_rejected(self, protocol):
        """중복 투표 방지."""
        protocol.submit_vote(_vote("rc1", "approve"))
        ok, reason = protocol.submit_vote(_vote("rc1", "reject"))
        assert not ok
        assert "중복" in reason

    def test_unregistered_voter_rejected(self, protocol):
        """미등록 투표자 거부."""
        ok, reason = protocol.submit_vote(_vote("hacker", "approve"))
        assert not ok
        assert "미등록" in reason

    def test_reset_clears_votes(self, protocol):
        protocol.submit_vote(_vote("rc1", "approve"))
        protocol.reset()
        assert len(protocol.submitted_voters) == 0

    def test_defense_passes_valid_consensus(self, defense):
        defense.protocol.submit_vote(_vote("rc1", "approve"))
        defense.protocol.submit_vote(_vote("rc8", "approve"))
        defense.protocol.submit_vote(_vote("rc9", "approve"))
        result = defense.validate()
        assert result.passed
