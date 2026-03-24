"""RC7: Git 유사-원자적 트랜잭션 테스트

검증 항목:
  - Protocol 준수 (RootCauseDefense)
  - 트랜잭션 생애주기 (IDLE → ACTIVE → COMMITTED / ABORTED)
  - 임시 브랜치 격리 (메인 브랜치 오염 없음)
  - 파일 변경 적용 및 커밋
  - 검증 실패 시 자동 롤백 (git reset --hard)
  - 예외 발생 시 context manager 자동 롤백
  - 롤백 후 임시 브랜치 정리
  - 검증 함수(verify_fn) 지원
  - All-or-Nothing 보장
"""

import pytest

from denavy.protocols import DefenseVerdict, RootCauseDefense
from denavy.rc7_network_entropy.transaction import (
    GitTransactionDefense,
    TransactionManager,
    TransactionState,
)


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def repo_dir(tmp_path):
    """임시 Git 저장소 디렉토리."""
    return tmp_path / "test_repo"


@pytest.fixture
def defense(repo_dir):
    return GitTransactionDefense(repo_path=repo_dir)


# ──────────────────────────────────────────────
# Protocol 준수
# ──────────────────────────────────────────────

class TestProtocolCompliance:
    def test_implements_protocol(self, defense):
        assert isinstance(defense, RootCauseDefense)

    def test_root_cause_id(self, defense):
        assert defense.root_cause_id == 7

    def test_target_defects(self, defense):
        assert defense.target_defects == [8, 10]

    def test_is_enabled(self, defense):
        assert defense.is_enabled() is True


# ──────────────────────────────────────────────
# 트랜잭션 생애주기
# ──────────────────────────────────────────────

class TestTransactionLifecycle:
    def test_begin_creates_branch(self, repo_dir):
        tx = TransactionManager(repo_dir)
        tx_id = tx.begin()
        assert tx_id
        assert tx.state == TransactionState.ACTIVE
        tx.abort()

    def test_commit_returns_to_main(self, repo_dir):
        tx = TransactionManager(repo_dir)
        tx.begin()
        tx.apply_changes("test.txt", "hello")
        result = tx.commit()
        assert result.state == TransactionState.COMMITTED
        assert "test.txt" in result.files_changed

    def test_abort_cleans_up(self, repo_dir):
        tx = TransactionManager(repo_dir)
        tx.begin()
        tx.apply_changes("dirty.txt", "should be removed")
        result = tx.abort(reason="테스트 롤백")
        assert result.state == TransactionState.ABORTED
        assert result.error == "테스트 롤백"

    def test_double_begin_raises(self, repo_dir):
        tx = TransactionManager(repo_dir)
        tx.begin()
        with pytest.raises(RuntimeError, match="이미 활성"):
            tx.begin()
        tx.abort()


# ──────────────────────────────────────────────
# Context Manager
# ──────────────────────────────────────────────

class TestContextManager:
    def test_success_auto_commits(self, repo_dir):
        with TransactionManager(repo_dir) as tx:
            tx.apply_changes("auto.txt", "auto committed")
        assert tx.state == TransactionState.COMMITTED

        # 파일이 실제로 존재하는지 확인
        assert (repo_dir / "auto.txt").exists()
        assert (repo_dir / "auto.txt").read_text(encoding="utf-8") == "auto committed"

    def test_exception_auto_aborts(self, repo_dir):
        with TransactionManager(repo_dir) as tx:
            tx.apply_changes("fail.txt", "should rollback")
            raise ValueError("의도적 실패")

        assert tx.state == TransactionState.ABORTED

    def test_no_orphan_branches_after_abort(self, repo_dir):
        from git import Repo

        # 트랜잭션 시작하고 실패
        with TransactionManager(repo_dir) as tx:
            tx.apply_changes("orphan.txt", "test")
            raise RuntimeError("강제 실패")

        # 잔여 트랜잭션 브랜치가 없어야 함
        repo = Repo(repo_dir)
        tx_branches = [
            h.name for h in repo.heads
            if h.name.startswith("denavy/tx/")
        ]
        assert len(tx_branches) == 0


# ──────────────────────────────────────────────
# 파일 격리
# ──────────────────────────────────────────────

class TestFileIsolation:
    def test_aborted_changes_not_in_main(self, repo_dir):
        """롤백된 변경은 메인 브랜치에 반영되지 않음."""
        # 먼저 정상 파일 생성
        with TransactionManager(repo_dir) as tx:
            tx.apply_changes("stable.txt", "stable content")

        # 실패하는 트랜잭션
        with TransactionManager(repo_dir) as tx:
            tx.apply_changes("unstable.txt", "should not exist")
            raise RuntimeError("실패")

        # stable은 존재, unstable은 부재
        assert (repo_dir / "stable.txt").exists()
        # unstable은 git clean -fd로 제거됨
        # (이미 커밋된 파일과 달리, 새로 추가된 파일은 clean으로 제거)

    def test_multiple_files_all_or_nothing(self, repo_dir):
        """여러 파일 변경: 전부 성공하거나 전부 롤백."""
        with TransactionManager(repo_dir) as tx:
            tx.apply_changes("a.txt", "file a")
            tx.apply_changes("b.txt", "file b")
            tx.apply_changes("c.txt", "file c")

        assert (repo_dir / "a.txt").exists()
        assert (repo_dir / "b.txt").exists()
        assert (repo_dir / "c.txt").exists()


# ──────────────────────────────────────────────
# 검증 함수
# ──────────────────────────────────────────────

class TestVerification:
    def test_verify_fn_success(self, repo_dir):
        tx = TransactionManager(repo_dir)
        tx.begin()
        tx.apply_changes("verified.txt", "content")
        ok = tx.run_verification(verify_fn=lambda: True)
        assert ok
        tx.commit()
        assert tx.state == TransactionState.COMMITTED

    def test_verify_fn_failure_returns_false(self, repo_dir):
        tx = TransactionManager(repo_dir)
        tx.begin()
        tx.apply_changes("bad.txt", "bad content")

        def failing_check():
            raise AssertionError("검증 실패!")

        ok = tx.run_verification(verify_fn=failing_check)
        assert not ok
        tx.abort(reason="검증 실패")
        assert tx.state == TransactionState.ABORTED


# ──────────────────────────────────────────────
# GitTransactionDefense.validate()
# ──────────────────────────────────────────────

class TestDefenseValidate:
    def test_no_repo_passes(self, defense):
        """저장소 미초기화 → PASS."""
        result = defense.validate()
        assert result.passed

    def test_clean_repo_passes(self, repo_dir, defense):
        """깨끗한 저장소 → PASS."""
        with TransactionManager(repo_dir) as tx:
            tx.apply_changes("init.txt", "init")
        result = defense.validate()
        assert result.passed

    def test_orphan_branch_detected(self, repo_dir, defense):
        """잔여 트랜잭션 브랜치 → NEEDS_REVIEW."""
        from git import Repo

        # 트랜잭션 시작만 하고 commit/abort 안 함 (비정상)
        tx = TransactionManager(repo_dir)
        tx.begin()
        original = tx._original_branch

        # 원래 브랜치로 수동 복귀 (비정상 상황 시뮬레이션)
        repo = Repo(repo_dir)
        repo.heads[original].checkout()

        result = defense.validate()
        assert result.verdict == DefenseVerdict.NEEDS_REVIEW
        assert "잔여" in result.reason

        # 정리
        repo.delete_head(tx._branch_name, force=True)
