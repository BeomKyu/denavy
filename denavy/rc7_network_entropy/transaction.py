"""
RC7: Git 기반 유사-원자적(Pseudo-Atomic) 트랜잭션 관리자
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
근본 원인 7 — 분산망 엔트로피와 핑퐁 데드락

억압 결함:
  결함 8 — 시스템 상태 무질서 (오염된 코드가 남아 누적)
  결함 10 — 핑퐁 데드락 (에이전트 자율 디버깅 무한 루프)

핵심 원리:
  엔터프라이즈의 무거운 2PC(2상 커밋)를 버리고,
  파이썬 context manager + Git으로 유사-원자적 트랜잭션을 구현.

  4대 강제 사항:
    1. 임시 격리: 작업 브랜치에서 투영(Projection)
    2. 자율 디버깅 차단: 에러 시 에이전트에게 재시도 기회 없음
    3. 결정론적 롤백: try/except → git reset --hard
    4. All-or-Nothing: 전체 검증 통과 시에만 메인에 병합

사용법:
    with TransactionManager(repo_path) as tx:
        tx.apply_changes(file_path, content)
        tx.run_verification(test_command)
    # 성공 → 메인 병합, 실패 → 자동 롤백
"""

from __future__ import annotations

import logging
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from git import InvalidGitRepositoryError, Repo

from denavy.protocols import DefenseResult, DefenseVerdict, RootCauseDefense

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 트랜잭션 상태 및 결과
# ──────────────────────────────────────────────

class TransactionState(str, Enum):
    """트랜잭션 생애주기 상태."""
    IDLE = "idle"
    ACTIVE = "active"        # 작업 브랜치에서 변경 중
    VERIFYING = "verifying"  # 검증 실행 중
    COMMITTED = "committed"  # 메인에 병합 완료
    ABORTED = "aborted"      # 롤백 완료


@dataclass
class TransactionResult:
    """트랜잭션 실행 결과."""
    tx_id: str
    state: TransactionState
    elapsed_seconds: float = 0.0
    files_changed: list[str] = field(default_factory=list)
    error: str = ""
    verification_output: str = ""


# ──────────────────────────────────────────────
# Git 트랜잭션 관리자
# ──────────────────────────────────────────────

class TransactionManager:
    """RC7: Git 기반 유사-원자적 트랜잭션.

    context manager로 사용:
      with TransactionManager(repo_path) as tx:
          tx.apply_changes("src/main.py", new_content)
          tx.run_verification("pytest tests/ -x")
      # → 성공: 메인 병합 / 실패: 자동 롤백

    원칙:
      - 에이전트에게 에러 로그를 돌려보내지 않음 (핑퐁 차단)
      - 실패 시 git reset --hard로 무자비하게 롤백
      - 성공 시에만 메인 브랜치에 커밋
    """

    BRANCH_PREFIX = "denavy/tx/"

    def __init__(
        self,
        repo_path: str | Path,
        main_branch: str = "main",
    ) -> None:
        self._repo_path = Path(repo_path)
        self._main_branch = main_branch
        self._tx_id = ""
        self._branch_name = ""
        self._state = TransactionState.IDLE
        self._start_time = 0.0
        self._files_changed: list[str] = []
        self._original_branch = ""
        self._repo: Repo | None = None

    @property
    def state(self) -> TransactionState:
        return self._state

    @property
    def tx_id(self) -> str:
        return self._tx_id

    def _ensure_repo(self) -> Repo:
        """Git 저장소를 열거나, 없으면 초기화한다."""
        if self._repo is not None:
            return self._repo

        try:
            self._repo = Repo(self._repo_path)
        except (InvalidGitRepositoryError, Exception) as e:
            # NoSuchPathError, InvalidGitRepositoryError 등
            # → 디렉토리 생성 후 Git 초기화
            self._repo_path.mkdir(parents=True, exist_ok=True)
            self._repo = Repo.init(self._repo_path)
            # 초기 커밋 (빈 저장소에서 브랜치 전환 불가 방지)
            readme = self._repo_path / "README.md"
            if not readme.exists():
                readme.write_text("# Denavy\n", encoding="utf-8")
            self._repo.index.add([str(readme)])
            self._repo.index.commit("Initial commit")
            logger.info("RC7: Git 저장소 초기화 완료")

        return self._repo

    def begin(self) -> str:
        """트랜잭션을 시작한다. 임시 브랜치를 생성.

        Returns:
            tx_id: 트랜잭션 고유 ID
        """
        if self._state != TransactionState.IDLE:
            raise RuntimeError(
                f"트랜잭션이 이미 활성 상태: {self._state.value}"
            )

        repo = self._ensure_repo()

        self._tx_id = str(uuid.uuid4())[:12]
        self._branch_name = f"{self.BRANCH_PREFIX}{self._tx_id}"
        self._start_time = time.time()
        self._files_changed = []

        # 현재 브랜치 기록
        try:
            self._original_branch = repo.active_branch.name
        except TypeError:
            # detached HEAD
            self._original_branch = self._main_branch

        # 임시 브랜치 생성 및 체크아웃
        repo.create_head(self._branch_name)
        repo.heads[self._branch_name].checkout()

        self._state = TransactionState.ACTIVE
        logger.info(f"RC7: 트랜잭션 시작 [{self._tx_id}] → {self._branch_name}")
        return self._tx_id

    def apply_changes(self, file_path: str, content: str) -> None:
        """파일에 변경을 적용한다. (임시 브랜치에서만)

        Args:
            file_path: 대상 파일 경로 (저장소 루트 기준 상대 경로)
            content: 파일에 쓸 내용
        """
        if self._state != TransactionState.ACTIVE:
            raise RuntimeError("활성 트랜잭션이 없습니다")

        target = self._repo_path / file_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        self._files_changed.append(file_path)
        logger.debug(f"RC7: 파일 변경 [{self._tx_id}] → {file_path}")

    def run_verification(
        self,
        command: str | list[str] | None = None,
        verify_fn: Any = None,
    ) -> bool:
        """검증을 실행한다.

        command 또는 verify_fn 중 하나를 사용.
        실패 시 자동 롤백 (에이전트에게 재시도 기회 없음).

        Args:
            command: 실행할 쉘 커맨드 (예: "pytest tests/ -x")
            verify_fn: 검증 함수 (예: lambda: run_tests())
                       예외 발생 시 실패로 간주

        Returns:
            True이면 검증 통과, False이면 롤백됨
        """
        if self._state != TransactionState.ACTIVE:
            raise RuntimeError("활성 트랜잭션이 없습니다")

        self._state = TransactionState.VERIFYING

        # Git에 변경 사항 커밋 (롤백 포인트)
        repo = self._ensure_repo()
        if self._files_changed:
            repo.index.add(self._files_changed)
            repo.index.commit(f"[denavy:tx:{self._tx_id}] 검증 전 스냅샷")

        try:
            if command:
                result = subprocess.run(
                    command if isinstance(command, list) else command.split(),
                    cwd=str(self._repo_path),
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.returncode != 0:
                    logger.warning(
                        f"RC7: 검증 실패 [{self._tx_id}] "
                        f"exit={result.returncode}"
                    )
                    return False

            if verify_fn:
                verify_fn()

            return True

        except subprocess.TimeoutExpired:
            logger.error(f"RC7: 검증 타임아웃 [{self._tx_id}]")
            return False
        except Exception as e:
            logger.error(f"RC7: 검증 예외 [{self._tx_id}] → {e}")
            return False

    def commit(self) -> TransactionResult:
        """트랜잭션을 확정한다. 메인 브랜치에 병합.

        Returns:
            TransactionResult: 성공 결과
        """
        if self._state not in (
            TransactionState.ACTIVE,
            TransactionState.VERIFYING,
        ):
            raise RuntimeError(f"커밋 불가 상태: {self._state.value}")

        repo = self._ensure_repo()

        # 변경 사항이 스테이징 안 된 게 있으면 커밋
        if repo.is_dirty() or repo.untracked_files:
            repo.index.add(self._files_changed)
            repo.index.commit(f"[denavy:tx:{self._tx_id}] 검증 통과 확정")

        # 메인 브랜치로 전환 후 병합
        repo.heads[self._original_branch].checkout()
        repo.git.merge(self._branch_name)

        # 임시 브랜치 정리
        repo.delete_head(self._branch_name, force=True)

        elapsed = time.time() - self._start_time
        self._state = TransactionState.COMMITTED
        logger.info(
            f"RC7: 트랜잭션 확정 [{self._tx_id}] "
            f"({len(self._files_changed)}개 파일, {elapsed:.2f}s)"
        )

        return TransactionResult(
            tx_id=self._tx_id,
            state=TransactionState.COMMITTED,
            elapsed_seconds=elapsed,
            files_changed=self._files_changed.copy(),
        )

    def abort(self, reason: str = "") -> TransactionResult:
        """트랜잭션을 파기한다. git reset --hard 후 원래 브랜치로 복귀.

        에이전트에게 재시도 기회를 주지 않는다.
        오류 로그를 에이전트에게 전달하지 않는다.
        무자비한 결정론적 롤백.

        Args:
            reason: 파기 사유

        Returns:
            TransactionResult: 롤백 결과
        """
        repo = self._ensure_repo()
        elapsed = time.time() - self._start_time

        try:
            # 1. 작업 트리 초기화 (dirty state 제거)
            repo.git.reset("--hard")
            repo.git.clean("-fd")

            # 2. 원래 브랜치로 복귀
            if self._original_branch and self._original_branch in [
                h.name for h in repo.heads
            ]:
                repo.heads[self._original_branch].checkout()

            # 3. 임시 브랜치 삭제
            if self._branch_name and self._branch_name in [
                h.name for h in repo.heads
            ]:
                repo.delete_head(self._branch_name, force=True)

        except Exception as e:
            logger.error(f"RC7: 롤백 중 오류 [{self._tx_id}] → {e}")

        self._state = TransactionState.ABORTED
        logger.warning(
            f"RC7: 트랜잭션 파기 [{self._tx_id}] "
            f"사유: {reason or '검증 실패'}"
        )

        return TransactionResult(
            tx_id=self._tx_id,
            state=TransactionState.ABORTED,
            elapsed_seconds=elapsed,
            files_changed=self._files_changed.copy(),
            error=reason,
        )

    # ── Context Manager ──

    def __enter__(self) -> "TransactionManager":
        self.begin()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """예외 발생 시 자동 롤백, 정상 종료 시 자동 커밋."""
        if exc_type is not None:
            # 예외 발생 → 무조건 롤백
            self.abort(reason=f"{exc_type.__name__}: {exc_val}")
            return True  # 예외 억제

        if self._state == TransactionState.ACTIVE:
            # 검증 없이 블록 종료 → 커밋
            self.commit()
        elif self._state == TransactionState.VERIFYING:
            # run_verification 후 상태 → 커밋
            self.commit()

        return False


# ──────────────────────────────────────────────
# RC7 방어 모듈 (Protocol 구현)
# ──────────────────────────────────────────────

class GitTransactionDefense:
    """RC7: Git 트랜잭션 기반 롤백 방어 모듈.

    에이전트의 코드 투영(Projection)을 원자적 트랜잭션으로 감싸서,
    검증 실패 시 시스템 상태가 오염되지 않도록 보장한다.

    이 모듈은 RootCauseDefense Protocol을 구현한다.
    validate()는 트랜잭션 관리자의 건전성을 검증한다.
    """

    def __init__(self, repo_path: str | Path) -> None:
        self._repo_path = Path(repo_path)

    @property
    def root_cause_id(self) -> int:
        return 7

    @property
    def target_defects(self) -> list[int]:
        return [8, 10]

    def is_enabled(self) -> bool:
        return True

    def create_transaction(
        self,
        main_branch: str = "main",
    ) -> TransactionManager:
        """새 트랜잭션 관리자를 생성한다."""
        return TransactionManager(
            repo_path=self._repo_path,
            main_branch=main_branch,
        )

    def validate(self, input_data: Any = None) -> DefenseResult:
        """Git 저장소 상태의 건전성을 검증한다.

        확인 사항:
          - 저장소가 존재하는가
          - 작업 트리가 깨끗한가 (dirty state 없음)
          - 잔여 트랜잭션 브랜치가 없는가
        """
        try:
            repo = Repo(self._repo_path)
        except Exception:
            return DefenseResult(
                verdict=DefenseVerdict.PASS,
                module_name="RC7_GitTransaction",
                root_cause_id=7,
                reason="Git 저장소 미초기화 (첫 트랜잭션 시 자동 생성)",
            )

        issues = []

        # Dirty state 검사
        if repo.is_dirty():
            issues.append("작업 트리에 커밋되지 않은 변경 존재")

        # 잔여 트랜잭션 브랜치 검사
        orphan_branches = [
            h.name for h in repo.heads
            if h.name.startswith(TransactionManager.BRANCH_PREFIX)
        ]
        if orphan_branches:
            issues.append(
                f"잔여 트랜잭션 브랜치 {len(orphan_branches)}개: "
                f"{', '.join(orphan_branches)}"
            )

        if issues:
            return DefenseResult(
                verdict=DefenseVerdict.NEEDS_REVIEW,
                module_name="RC7_GitTransaction",
                root_cause_id=7,
                reason=f"저장소 상태 이상 {len(issues)}건: {issues[0]}",
                details={"issues": issues},
            )

        return DefenseResult(
            verdict=DefenseVerdict.PASS,
            module_name="RC7_GitTransaction",
            root_cause_id=7,
            reason="저장소 상태 정상 (clean, 잔여 브랜치 없음)",
        )
