"""
전역 설정
━━━━━━━━
환경변수, 경로, 기본값 등 프로젝트 전역 설정을 관리한다.
모든 설정은 Pydantic BaseSettings를 통해 검증된다.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


# 프로젝트 루트 디렉토리 (이 파일의 부모의 부모)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 런타임 데이터 디렉토리
DATA_DIR = PROJECT_ROOT / "data"


class DenavySettings(BaseSettings):
    """Denavy 전역 설정.

    환경변수로 오버라이드 가능. 접두사: DENAVY_
    예: DENAVY_DEFAULT_MODEL="gpt-4o-mini"
    """

    model_config = {"env_prefix": "DENAVY_", "env_file": ".env"}

    # ── LLM 설정 ──
    default_model: str = Field(
        default="gpt-4o-mini",
        description="기본 LLM 모델명 (litellm 형식)"
    )

    # ── 데이터 경로 ──
    data_dir: Path = Field(default=DATA_DIR)
    activity_log: Path = Field(default=DATA_DIR / "activity.jsonl")
    roadmap_file: Path = Field(default=DATA_DIR / "roadmap.json")

    # ── Deno 샌드박스 ──
    deno_deploy_token: str = Field(
        default="",
        description="Deno Deploy 액세스 토큰"
    )
    sandbox_timeout: int = Field(
        default=30,
        description="샌드박스 실행 타임아웃(초)"
    )

    # ── 파이프라인 제어 ──
    max_retry_on_reject: int = Field(
        default=3,
        description="검증 거부 시 최대 재시도 횟수"
    )

    def ensure_data_dir(self) -> None:
        """data 디렉토리가 없으면 생성한다."""
        self.data_dir.mkdir(parents=True, exist_ok=True)


# 싱글톤 설정 인스턴스
settings = DenavySettings()
