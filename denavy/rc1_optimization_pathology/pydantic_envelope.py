"""
RC1: Pydantic/Instructor JSON 봉투 강제 모듈
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
근본 원인 1 — 보상 최적화의 병리적 편향 (Optimization Pathology)

억압 결함:
  결함 1 — 극단적 게으름: 수천 줄을 단일 파일에 밀어넣거나 주석으로 생략
  결함 2 — 무지성 아부: 틀린 논리에 동조하는 기만적 정렬

에이전트의 출력을 자유로운 텍스트가 아닌, 엄격한 Pydantic BaseModel
JSON 봉투로 강제하여 의도의 구조적 무결성을 검증한다.
Instructor 패키지를 통해 LLM이 반드시 이 스키마를 따르도록 한다.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from denavy.protocols import DefenseResult, DefenseVerdict, RootCauseDefense


# ──────────────────────────────────────────────
# 의도 이벤트 스키마 (Intention Payload)
# ──────────────────────────────────────────────

class ActionType(str, Enum):
    """에이전트가 수행 가능한 행위의 허용 목록."""
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"


class CodeChange(BaseModel):
    """단일 코드 변경 단위 (diff 수준).

    에이전트는 전체 파일을 덮어쓰는 것이 아니라,
    반드시 변경 '단위'를 명시해야 한다.
    """
    target_line_start: int = Field(
        ..., ge=1,
        description="변경 시작 라인 번호 (1-indexed)"
    )
    target_line_end: int = Field(
        ..., ge=1,
        description="변경 종료 라인 번호 (1-indexed, inclusive)"
    )
    original_content: str = Field(
        ..., min_length=0,
        description="변경 전 원본 코드 (빈 문자열 = 신규 삽입)"
    )
    new_content: str = Field(
        ...,
        description="변경 후 코드"
    )
    rationale: str = Field(
        ..., min_length=10,
        description="이 변경의 근거 (최소 10자 — 게으른 생략 방지)"
    )

    @field_validator("target_line_end")
    @classmethod
    def end_after_start(cls, v: int, info: Any) -> int:
        start = info.data.get("target_line_start")
        if start is not None and v < start:
            raise ValueError(
                f"target_line_end({v})는 target_line_start({start}) "
                "이상이어야 합니다"
            )
        return v


class IntentionPayload(BaseModel):
    """에이전트의 의도를 담는 JSON 봉투.

    LLM 에이전트는 자유로운 텍스트 대신 반드시 이 구조체를
    출력해야 한다. Instructor가 이를 강제한다.

    결함 1 (게으름) 방어:
      - reasoning 필수 (최소 20자)
      - code_changes 비어있을 수 없음
      - 단일 파일 내 프레젠테이션 + 비즈니스 로직 혼합 금지

    결함 2 (아부) 방어:
      - confidence_score 강제 (맹목적 동의 감지용)
      - dissenting_considerations 필수 (반론 필드)
    """

    # ── 필수 메타데이터 ──
    task_id: str = Field(
        ..., min_length=1,
        description="이 의도가 속한 태스크 식별자"
    )
    target_file: str = Field(
        ..., min_length=1,
        description="변경 대상 파일 경로"
    )
    action: ActionType = Field(
        ...,
        description="수행할 행위 (create / modify / delete)"
    )

    # ── 게으름(결함 1) 방어 필드 ──
    reasoning: str = Field(
        ..., min_length=20,
        description="변경 근거 (최소 20자 — 게으른 생략 원천 차단)"
    )
    code_changes: list[CodeChange] = Field(
        ..., min_length=1,
        description="변경 단위 목록 (비어 있을 수 없음)"
    )

    # ── 아부(결함 2) 방어 필드 ──
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0,
        description="이 변경에 대한 자신감 점수 (0.0~1.0)"
    )
    dissenting_considerations: str = Field(
        ..., min_length=10,
        description=(
            "이 변경에 대한 반론 또는 우려 사항 "
            "(최소 10자 — 맹목적 동의 방지)"
        ),
    )

    # ── 파일 경로 유효성 ──
    @field_validator("target_file")
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        """위험한 경로 패턴을 사전 차단한다."""
        # 경로 순회 공격 방지
        if ".." in v:
            raise ValueError("경로 순회(..)는 허용되지 않습니다")

        # 절대 경로 강제 또는 상대 경로 허용 여부
        # 운영체제에 따라 다르므로 기본적인 위험 패턴만 차단
        dangerous_patterns = [
            r"^/etc/",
            r"^/root/",
            r"^C:\\Windows\\",
            r"^/dev/",
        ]
        for pattern in dangerous_patterns:
            if re.match(pattern, v, re.IGNORECASE):
                raise ValueError(
                    f"시스템 경로 접근이 차단되었습니다: {v}"
                )
        return v

    # ── 모델 수준 교차 검증 ──
    @model_validator(mode="after")
    def cross_validate(self) -> "IntentionPayload":
        """모델 전체 수준의 교차 검증을 수행한다."""

        # delete 액션에 code_changes가 있으면 모순
        if self.action == ActionType.DELETE:
            for change in self.code_changes:
                if change.new_content.strip():
                    raise ValueError(
                        "DELETE 액션에서 new_content가 비어있지 않습니다. "
                        "삭제 의도와 새 코드 작성이 모순됩니다."
                    )

        # 낮은 confidence에서 강한 변경은 경고
        if self.confidence_score < 0.3 and len(self.code_changes) > 5:
            raise ValueError(
                f"confidence_score({self.confidence_score})가 매우 낮은데 "
                f"{len(self.code_changes)}개의 대규모 변경을 시도합니다. "
                "확신 없는 대규모 변경은 거부됩니다."
            )

        return self


# ──────────────────────────────────────────────
# RC1 방어 모듈 구현체
# ──────────────────────────────────────────────

class PydanticEnvelopeDefense:
    """RC1: Pydantic JSON 봉투 방어 모듈.

    에이전트의 자유 텍스트 출력을 IntentionPayload 스키마로
    강제 파싱하여 구조적 무결성을 검증한다.

    이 모듈은 RootCauseDefense Protocol을 구현한다.
    """

    @property
    def root_cause_id(self) -> int:
        return 1

    @property
    def target_defects(self) -> list[int]:
        return [1, 2]  # 게으름, 아부

    def is_enabled(self) -> bool:
        return True

    def validate(self, input_data: Any) -> DefenseResult:
        """입력 데이터를 IntentionPayload로 파싱/검증한다.

        Args:
            input_data: dict 또는 JSON 문자열 또는 IntentionPayload

        Returns:
            DefenseResult: pass이면 검증 통과, reject이면 즉시 거부
        """
        try:
            if isinstance(input_data, IntentionPayload):
                payload = input_data
            elif isinstance(input_data, dict):
                payload = IntentionPayload.model_validate(input_data)
            elif isinstance(input_data, str):
                payload = IntentionPayload.model_validate_json(input_data)
            else:
                return DefenseResult(
                    verdict=DefenseVerdict.REJECT,
                    module_name="RC1_PydanticEnvelope",
                    root_cause_id=1,
                    reason=f"지원하지 않는 입력 타입: {type(input_data).__name__}",
                )

            return DefenseResult(
                verdict=DefenseVerdict.PASS,
                module_name="RC1_PydanticEnvelope",
                root_cause_id=1,
                reason="의도 봉투 검증 통과",
                details={"payload": payload.model_dump()},
            )

        except Exception as e:
            return DefenseResult(
                verdict=DefenseVerdict.REJECT,
                module_name="RC1_PydanticEnvelope",
                root_cause_id=1,
                reason=f"의도 봉투 검증 실패: {e}",
                details={"error_type": type(e).__name__, "error": str(e)},
            )
