"""
RC9: IntentShield 이중 평면 격리 방어 모듈
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
근본 원인 9 — 분산 보안 경계의 붕괴와 위상학적 정보 감염
  (Collapse of Security Boundaries & Topological Contagion)

억압 결함:
  결함 19 — 프롬프트 감염 및 은닉 채널 형성

핵심 원리:
  LLM은 수동적 '데이터(Data)'와 실행 가능한 '명령어(Instruction)'를
  구별하지 못하는 위상학적 구조 결함을 가진다. IntentShield는
  하드웨어의 하버드 구조(Harvard Architecture) 개념을 차용하여
  입력 파이프라인을 명령 제어 평면(Control Plane)과
  데이터 평면(Data Plane)으로 강제 격리한다.

IntentShield의 결정론적 방어 메커니즘:
  1. CoreSafety — 셸 실행/파일 삭제/도메인 접근/악성 구문 차단
     (정규식 + 문자열 매칭, 머신러닝 배제)
  2. Conscience — 기만/유해성/보안 우회/IP 유출 차단
  3. 해시 무결성 — SHA-256으로 소스 코드 밀봉, 변조 시 os._exit(1)
  4. FrozenNamespace — 런타임 상수 덮어쓰기 물리적 차단
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from intentshield import IntentShield

from denavy.protocols import DefenseResult, DefenseVerdict, RootCauseDefense

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# RC1 IntentionPayload.action → IntentShield action_type 매핑
# ──────────────────────────────────────────────

# 우리 파이프라인에서 에이전트는 *의도 이벤트*를 생성할 뿐,
# 파일 시스템에 직접 쓰지 않는다. 따라서:
#   - create/modify → THINK: 코드 내용의 악성 구문만 검사
#     (WRITE_FILE은 파일 확장자 제한(.txt/.md/.json 등만 허용)이 있어
#      .py 등 소스 파일 의도를 거부해버림)
#   - delete → DELETE_FILE: CoreSafety가 영구 차단 (ALLOW_FILE_DELETION=False)
_ACTION_MAP: dict[str, str] = {
    "create": "THINK",
    "modify": "THINK",
    "delete": "DELETE_FILE",
}



# 프로세스 단위 싱글톤 캐시
_SHARED_INSTANCE: Any = None


class IntentShieldDefense:
    """RC9: IntentShield 기반 이중 평면 격리 방어 모듈.

    LLM 에이전트의 의도(Intent)가 시스템에 도달하기 전,
    결정론적 정규식/문자열 매칭으로 악성 행위를 사전 차단한다.

    이 모듈은 RootCauseDefense Protocol을 구현한다.

    Features:
        - CoreSafety: 셸 인젝션, SQL 인젝션, XSS, 역방향 셸 등 차단
        - Conscience: 기만/유해성/보안 우회/IP 유출 차단
        - 해시 무결성: data/.core_safety_lock, data/.conscience_lock
        - FrozenNamespace: 보안 상수 런타임 불변성 보장
        - 0ms 지연: 모든 검사는 정규식 기반 서브밀리초 완료
    """

    def __init__(
        self,
        data_dir: str | Path = "data",
        restricted_domains: list[str] | None = None,
        protected_files: list[str] | None = None,
    ) -> None:
        """IntentShield를 초기화하고 해시 무결성 봉인을 수행한다.

        Args:
            data_dir: lock 파일 저장 디렉토리
            restricted_domains: 추가 차단 도메인 목록
            protected_files: 읽기/쓰기 금지 파일 경로 목록
        """
        self._data_dir = str(data_dir)

        # IntentShield 인스턴스 생성 및 봉인
        # valid_tools: 우리 파이프라인에서 허용하는 액션만 화이트리스트
        self._shield = IntentShield(
            data_dir=self._data_dir,
            valid_tools=["WRITE_FILE", "DELETE_FILE", "ANSWER", "THINK"],
            restricted_domains=restricted_domains,
            protected_files=protected_files,
            # exempt_actions: 우리 파이프라인 내부 액션은
            # Conscience의 _FAKE_TOOL_PATTERN 면제
            exempt_actions={"WRITE_FILE", "DELETE_FILE", "THINK"},
        )

        # SHA-256 해시 밀봉 — 최초 실행 시 lock 파일 생성,
        # 이후 실행 시 소스 코드 변조 감지 → os._exit(1) 강제 종료
        self._shield.initialize()
        logger.info(
            "RC9 IntentShield 봉인 완료 "
            f"(data_dir={self._data_dir})"
        )

    @classmethod
    def get_shared_instance(
        cls,
        data_dir: str | Path = "data",
        **kwargs: Any,
    ) -> "IntentShieldDefense":
        """프로세스 단위 싱글톤 인스턴스를 반환한다.

        IntentShield의 _SELF_HASH 보호 때문에
        같은 프로세스에서 여러 번 생성하면 TypeError가 발생.
        이 메서드는 최초 1회만 인스턴스를 생성하고 이후 재사용.
        """
        global _SHARED_INSTANCE
        if _SHARED_INSTANCE is None:
            _SHARED_INSTANCE = cls(data_dir=data_dir, **kwargs)
        return _SHARED_INSTANCE

    @property
    def root_cause_id(self) -> int:
        return 9

    @property
    def target_defects(self) -> list[int]:
        return [19]  # 프롬프트 감염 및 은닉 채널

    def is_enabled(self) -> bool:
        return True

    def validate(self, input_data: Any) -> DefenseResult:
        """에이전트의 의도를 IntentShield로 감사(Audit)한다.

        IntentShield는 머신러닝이 아닌 결정론적 정규식/문자열 매칭만으로
        다음을 검사한다:
          - 셸 인젝션 (rm -rf, nc -e, powershell, subprocess 등)
          - SQL 인젝션 (DROP TABLE, UNION SELECT 등)
          - XSS (<script>, document.cookie 등)
          - 역방향 셸 (socket, pty.spawn 등)
          - 코드 탈취 시도 (class CoreSafety, my source code 등)
          - 보안 우회 시도 (BYPASS, IGNORE DIRECTIVE 등)
          - 유해성 키워드 (KILL, DESTROY, HACK 등)
          - 도메인 블랙리스트 (darkweb, .onion 등)

        Args:
            input_data: 다음 중 하나:
              - dict: {"action": "modify", "payload": "...", "target_file": "..."}
              - IntentionPayload 인스턴스 (model_dump() 후 처리)
              - str: 원시 텍스트 (payload로 감사)

        Returns:
            DefenseResult: pass이면 안전, reject이면 악성 의도 탐지
        """
        try:
            action_type, payload, invoker_role = self._extract_audit_params(
                input_data
            )

            # IntentShield audit — CoreSafety + Conscience 2중 검사
            # rate_limit_interval은 CoreSafety 내부에서 처리됨 (기본 0.5s)
            ok, reason = self._shield.audit(
                action_type=action_type,
                payload=payload,
                invoker_role=invoker_role,
            )

            if ok:
                return DefenseResult(
                    verdict=DefenseVerdict.PASS,
                    module_name="RC9_IntentShield",
                    root_cause_id=9,
                    reason="의도 보안 감사 통과",
                    details={
                        "action_type": action_type,
                        "shield_reason": reason,
                    },
                )
            else:
                logger.warning(
                    f"RC9 IntentShield 차단: {reason} "
                    f"(action={action_type})"
                )
                return DefenseResult(
                    verdict=DefenseVerdict.REJECT,
                    module_name="RC9_IntentShield",
                    root_cause_id=9,
                    reason=f"보안 위반 탐지: {reason}",
                    details={
                        "action_type": action_type,
                        "shield_reason": reason,
                    },
                )

        except Exception as e:
            logger.error(f"RC9 IntentShield 오류: {e}")
            # Fail-closed: 오류 시 안전하게 거부
            return DefenseResult(
                verdict=DefenseVerdict.REJECT,
                module_name="RC9_IntentShield",
                root_cause_id=9,
                reason=f"보안 감사 오류 (fail-closed): {e}",
                details={"error_type": type(e).__name__, "error": str(e)},
            )

    def _extract_audit_params(
        self, input_data: Any
    ) -> tuple[str, str, str]:
        """입력 데이터에서 IntentShield audit 파라미터를 추출한다.

        Returns:
            (action_type, payload, invoker_role) 튜플
        """
        if isinstance(input_data, dict):
            # RC1의 IntentionPayload.model_dump() 결과 또는 유사 dict
            raw_action = input_data.get("action", "THINK")
            action_type = _ACTION_MAP.get(raw_action, raw_action.upper())

            # payload 구성: 코드 변경 내용 + 파일 경로 + reasoning
            parts = []
            if target_file := input_data.get("target_file", ""):
                parts.append(f"file:{target_file}")
            if reasoning := input_data.get("reasoning", ""):
                parts.append(reasoning)
            for change in input_data.get("code_changes", []):
                if isinstance(change, dict):
                    parts.append(change.get("new_content", ""))
                else:
                    # Pydantic 모델인 경우
                    parts.append(getattr(change, "new_content", ""))
            payload = "\n".join(parts)

            invoker_role = input_data.get("invoker_role", "agent")
            return action_type, payload, invoker_role

        elif isinstance(input_data, str):
            # 원시 텍스트 — THINK 액션으로 감사
            return "THINK", input_data, "agent"

        elif hasattr(input_data, "model_dump"):
            # Pydantic BaseModel 인스턴스
            return self._extract_audit_params(input_data.model_dump())

        else:
            raise TypeError(
                f"지원하지 않는 입력 타입: {type(input_data).__name__}"
            )
