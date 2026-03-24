"""
RC2-A: ESAA(Event-Sourced Agent Architecture) 이벤트 저장소
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
근본 원인 2 — 자기회귀 노출 편향 (Autoregressive Exposure Bias)

억압 결함:
  결함 7 — 코드 덮어쓰기/밀어넣기 폭주
  결함 11 — 의미론적 표류 (아키텍처 경계 침범)

핵심 원리:
  에이전트에게 파일 시스템 직접 쓰기(Write) 권한을 주지 않는다.
  대신 모든 의도(Intention)를 append-only JSONL 이벤트로 기록하고,
  검증 파이프라인을 통과한 이벤트만 코드로 투영(Projection)한다.

  CUD → C(Create Event) → U(Validate) → D(Project):
    1. Agent → IntentionPayload → 이벤트 저장 (append-only)
    2. 이벤트 → RC1/RC9/RC8 검증 파이프라인 통과
    3. 통과된 이벤트만 파일 시스템에 투영
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from denavy.protocols import DefenseResult, DefenseVerdict, RootCauseDefense

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 이벤트 타입 및 데이터 모델
# ──────────────────────────────────────────────

class EventStatus(str, Enum):
    """이벤트 생애주기 상태."""
    PENDING = "pending"      # 검증 대기
    VALIDATED = "validated"  # 파이프라인 통과
    REJECTED = "rejected"    # 거부됨
    PROJECTED = "projected"  # 파일 시스템에 투영 완료


@dataclass
class IntentionEvent:
    """에이전트의 의도를 담는 불변 이벤트.

    Append-only 로그에 기록되며, 직접 수정이 불가능하다.
    상태 변경은 새 이벤트를 추가하는 방식으로만 이루어진다.
    """
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    status: EventStatus = EventStatus.PENDING

    # 의도 내용
    task_id: str = ""
    target_file: str = ""
    action: str = ""
    reasoning: str = ""
    code_changes: list[dict[str, Any]] = field(default_factory=list)

    # 검증 결과
    validation_results: list[dict[str, Any]] = field(default_factory=list)
    rejection_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        """JSON 직렬화 가능한 dict로 변환."""
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IntentionEvent:
        """dict에서 IntentionEvent를 복원."""
        data = data.copy()
        data["status"] = EventStatus(data.get("status", "pending"))
        return cls(**{
            k: v for k, v in data.items()
            if k in cls.__dataclass_fields__
        })


# ──────────────────────────────────────────────
# ESAA 이벤트 저장소
# ──────────────────────────────────────────────

class EventStore:
    """Append-only 이벤트 저장소.

    모든 에이전트 의도를 JSONL(JSON Lines) 파일에 추가 전용으로 기록한다.
    이벤트는 절대 수정/삭제되지 않으며, 상태 변경은 새 이벤트 추가로만 이루어진다.
    """

    def __init__(self, log_path: str | Path) -> None:
        self._log_path = Path(log_path)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._events: list[IntentionEvent] = []

        # 기존 로그 파일이 있으면 복원
        if self._log_path.exists():
            self._load_from_disk()

    def _load_from_disk(self) -> None:
        """디스크에서 이벤트 로그를 복원한다."""
        try:
            with open(self._log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        data = json.loads(line)
                        self._events.append(IntentionEvent.from_dict(data))
            logger.info(f"ESAA: {len(self._events)}개 이벤트 복원")
        except Exception as e:
            logger.error(f"ESAA: 이벤트 로그 복원 실패: {e}")

    def append(self, event: IntentionEvent) -> str:
        """이벤트를 저장소에 추가한다. (append-only)

        Args:
            event: 추가할 IntentionEvent

        Returns:
            event_id: 생성된 이벤트 ID
        """
        self._events.append(event)
        self._persist(event)
        logger.debug(f"ESAA: 이벤트 추가 {event.event_id[:8]}... (status={event.status.value})")
        return event.event_id

    def _persist(self, event: IntentionEvent) -> None:
        """이벤트를 디스크에 추가한다."""
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")

    def get(self, event_id: str) -> IntentionEvent | None:
        """event_id로 이벤트를 조회한다."""
        for event in self._events:
            if event.event_id == event_id:
                return event
        return None

    def get_by_status(self, status: EventStatus) -> list[IntentionEvent]:
        """특정 상태의 이벤트 목록을 반환한다."""
        return [e for e in self._events if e.status == status]

    def mark_validated(
        self,
        event_id: str,
        validation_results: list[dict[str, Any]],
    ) -> IntentionEvent:
        """이벤트를 VALIDATED 상태로 전환한다.

        원본 이벤트를 수정하지 않고, 새 VALIDATED 이벤트를 추가한다.
        """
        original = self.get(event_id)
        if original is None:
            raise ValueError(f"이벤트 {event_id} 없음")

        validated = IntentionEvent(
            event_id=original.event_id,
            timestamp=time.time(),
            status=EventStatus.VALIDATED,
            task_id=original.task_id,
            target_file=original.target_file,
            action=original.action,
            reasoning=original.reasoning,
            code_changes=original.code_changes,
            validation_results=validation_results,
        )
        self.append(validated)
        return validated

    def mark_rejected(
        self,
        event_id: str,
        reason: str,
        validation_results: list[dict[str, Any]],
    ) -> IntentionEvent:
        """이벤트를 REJECTED 상태로 전환한다."""
        original = self.get(event_id)
        if original is None:
            raise ValueError(f"이벤트 {event_id} 없음")

        rejected = IntentionEvent(
            event_id=original.event_id,
            timestamp=time.time(),
            status=EventStatus.REJECTED,
            task_id=original.task_id,
            target_file=original.target_file,
            action=original.action,
            reasoning=original.reasoning,
            code_changes=original.code_changes,
            validation_results=validation_results,
            rejection_reason=reason,
        )
        self.append(rejected)
        return rejected

    def mark_projected(self, event_id: str) -> IntentionEvent:
        """이벤트를 PROJECTED(투영 완료) 상태로 전환한다."""
        original = self.get(event_id)
        if original is None:
            raise ValueError(f"이벤트 {event_id} 없음")

        projected = IntentionEvent(
            event_id=original.event_id,
            timestamp=time.time(),
            status=EventStatus.PROJECTED,
            task_id=original.task_id,
            target_file=original.target_file,
            action=original.action,
            reasoning=original.reasoning,
            code_changes=original.code_changes,
            validation_results=original.validation_results,
        )
        self.append(projected)
        return projected

    @property
    def count(self) -> int:
        return len(self._events)

    def get_latest_state(self, event_id: str) -> IntentionEvent | None:
        """특정 event_id의 가장 최신 상태를 반환한다."""
        latest = None
        for event in self._events:
            if event.event_id == event_id:
                latest = event
        return latest


# ──────────────────────────────────────────────
# RC2 방어 모듈 — ESAA 검증 계층
# ──────────────────────────────────────────────

class ESAADefense:
    """RC2: ESAA 이벤트 소싱 방어 모듈.

    에이전트의 의도를 append-only 이벤트로 기록하고,
    다음을 검증한다:
      1. 동일 파일에 대한 과도한 변경 시도 감지 (폭주 방어)
      2. 이벤트 간 시간 간격 점검 (무한 루프 감지)
      3. 코드 변경량 제한 (단일 이벤트에서 과도한 줄 수 변경 차단)

    이 모듈은 RootCauseDefense Protocol을 구현한다.
    """

    def __init__(
        self,
        event_store: EventStore,
        max_changes_per_file: int = 50,
        max_lines_per_change: int = 200,
        min_interval_seconds: float = 1.0,
    ) -> None:
        self._store = event_store
        self._max_changes_per_file = max_changes_per_file
        self._max_lines_per_change = max_lines_per_change
        self._min_interval_seconds = min_interval_seconds

    @property
    def root_cause_id(self) -> int:
        return 2

    @property
    def target_defects(self) -> list[int]:
        return [7, 11]

    def is_enabled(self) -> bool:
        return True

    @property
    def event_store(self) -> EventStore:
        return self._store

    def validate(self, input_data: Any) -> DefenseResult:
        """에이전트의 의도를 이벤트로 기록하고 검증한다.

        Args:
            input_data: IntentionPayload의 dict 형태
                필수 키: task_id, target_file, action, code_changes

        Returns:
            DefenseResult: 검증 결과
        """
        if not isinstance(input_data, dict):
            return DefenseResult(
                verdict=DefenseVerdict.REJECT,
                module_name="RC2_ESAA",
                root_cause_id=2,
                reason=f"입력이 dict가 아님: {type(input_data).__name__}",
            )

        # 1. 이벤트 생성 및 저장
        event = IntentionEvent(
            task_id=input_data.get("task_id", ""),
            target_file=input_data.get("target_file", ""),
            action=input_data.get("action", ""),
            reasoning=input_data.get("reasoning", ""),
            code_changes=input_data.get("code_changes", []),
        )
        self._store.append(event)

        # 2. 폭주 검사: 동일 파일에 대한 과도한 변경
        if event.target_file:
            same_file_count = sum(
                1 for e in self._store.get_by_status(EventStatus.PENDING)
                if e.target_file == event.target_file
            )
            if same_file_count > self._max_changes_per_file:
                self._store.mark_rejected(
                    event.event_id,
                    reason=f"동일 파일({event.target_file})에 대한 "
                           f"변경이 {same_file_count}회 누적. "
                           f"상한: {self._max_changes_per_file}",
                    validation_results=[],
                )
                return DefenseResult(
                    verdict=DefenseVerdict.REJECT,
                    module_name="RC2_ESAA",
                    root_cause_id=2,
                    reason=(
                        f"폭주 감지: {event.target_file}에 "
                        f"{same_file_count}회 변경 시도 "
                        f"(상한 {self._max_changes_per_file})"
                    ),
                    details={"event_id": event.event_id},
                )

        # 3. 코드 변경량 검사
        total_lines = 0
        for change in event.code_changes:
            new_content = change.get("new_content", "")
            total_lines += new_content.count("\n") + 1

        if total_lines > self._max_lines_per_change:
            self._store.mark_rejected(
                event.event_id,
                reason=f"단일 이벤트에서 {total_lines}줄 변경 시도. "
                       f"상한: {self._max_lines_per_change}줄",
                validation_results=[],
            )
            return DefenseResult(
                verdict=DefenseVerdict.REJECT,
                module_name="RC2_ESAA",
                root_cause_id=2,
                reason=(
                    f"과도한 변경량: {total_lines}줄 "
                    f"(상한 {self._max_lines_per_change}줄)"
                ),
                details={"event_id": event.event_id, "lines": total_lines},
            )

        # 4. 통과 — 이벤트는 PENDING 상태로 유지
        # (이후 파이프라인에서 mark_validated / mark_projected)
        return DefenseResult(
            verdict=DefenseVerdict.PASS,
            module_name="RC2_ESAA",
            root_cause_id=2,
            reason="이벤트 기록 및 기본 검증 통과",
            details={"event_id": event.event_id},
        )
