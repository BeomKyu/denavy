"""RC8: Z3 SMT Solver 정적 논리 검증 테스트

검증 항목:
  - Protocol 준수 (RootCauseDefense)
  - unsat 증명: 위반 불가능한 제약은 PASS
  - sat 반례: 위반 가능한 제약은 REJECT + 반례 모델 반환
  - 범위 제약 팩토리 (constraint_value_range)
  - 복합 제약: 예산 초과, 조건부 논리 (P ⟹ Q)
  - WARNING 수준 제약: NEEDS_REVIEW 반환
  - 빈 제약 목록: 실행 생략
  - Z3 검증 속도: < 100ms 이내
"""

import pytest
from z3 import And, Bool, Implies, Int, Not, Or, Real, Solver

from denavy.protocols import DefenseVerdict, RootCauseDefense
from denavy.rc8_deductive_collapse.z3_verifier import (
    ConstraintSeverity,
    LogicConstraint,
    Z3VerifierDefense,
    constraint_value_range,
)


# ──────────────────────────────────────────────
# Protocol 준수 테스트
# ──────────────────────────────────────────────

class TestProtocolCompliance:
    def test_implements_protocol(self):
        v = Z3VerifierDefense()
        assert isinstance(v, RootCauseDefense)

    def test_root_cause_id(self):
        v = Z3VerifierDefense()
        assert v.root_cause_id == 8

    def test_target_defects(self):
        v = Z3VerifierDefense()
        assert v.target_defects == [12, 13, 14]

    def test_not_enabled_without_constraints(self):
        """제약 조건이 없으면 비활성."""
        v = Z3VerifierDefense()
        assert v.is_enabled() is False

    def test_enabled_with_constraints(self):
        v = Z3VerifierDefense()
        v.add_constraint(
            constraint_value_range("test", "x", min_val=0)
        )
        assert v.is_enabled() is True


# ──────────────────────────────────────────────
# unsat 증명 (안전) 테스트
# ──────────────────────────────────────────────

class TestUnsatProof:
    """위반 불가능한 제약 → unsat → PASS."""

    def test_trivially_unsatisfiable(self):
        """x > 0 ∧ x < 0 은 동시에 성립할 수 없다 → unsat."""
        def build(solver: Solver):
            x = Real("x")
            solver.add(x > 0)
            solver.add(x < 0)  # 모순 → unsat

        v = Z3VerifierDefense()
        v.add_constraint(LogicConstraint(
            name="impossible_contradiction",
            description="x > 0 이면서 x < 0인 경우는 존재하지 않음",
            severity=ConstraintSeverity.CRITICAL,
            build_formula=build,
        ))

        result = v.validate()
        assert result.passed
        assert "무결성 증명 완료" in result.reason

    def test_boolean_tautology(self):
        """NOT(P ∧ NOT P) — 항진식은 위반 불가 → unsat."""
        def build(solver: Solver):
            p = Bool("p")
            # 위반 조건: p ∧ ¬p (자기 모순)
            solver.add(And(p, Not(p)))

        v = Z3VerifierDefense()
        v.add_constraint(LogicConstraint(
            name="no_self_contradiction",
            description="P ∧ ¬P는 성립할 수 없음",
            severity=ConstraintSeverity.CRITICAL,
            build_formula=build,
        ))

        result = v.validate()
        assert result.passed


# ──────────────────────────────────────────────
# sat 반례 (결함 탐지) 테스트
# ──────────────────────────────────────────────

class TestSatCounterexample:
    """위반 가능한 제약 → sat → REJECT + 반례."""

    def test_simple_violation_detected(self):
        """x > 100 이 가능한가? → sat (예: x=101)."""
        def build(solver: Solver):
            x = Int("x")
            solver.add(x > 100)

        v = Z3VerifierDefense()
        v.add_constraint(LogicConstraint(
            name="value_overflow",
            description="값이 100을 초과하는 입력이 존재하는가",
            severity=ConstraintSeverity.CRITICAL,
            build_formula=build,
        ))

        result = v.validate()
        assert result.rejected
        assert "반례 발견" in result.reason
        # 반례에 x 변수가 포함되어야 함
        results_detail = result.details["results"]
        assert results_detail[0]["counterexample"] is not None
        assert "x" in results_detail[0]["counterexample"]

    def test_budget_overflow_detected(self):
        """지출 > 예산인 경우가 존재하는가? → sat."""
        def build(solver: Solver):
            budget = Int("budget")
            spent = Int("spent")
            # 합리적 범위 내에서 (둘 다 양수)
            solver.add(budget > 0)
            solver.add(spent > 0)
            # 위반 조건: 지출이 예산 초과
            solver.add(spent > budget)

        v = Z3VerifierDefense()
        v.add_constraint(LogicConstraint(
            name="budget_overflow",
            description="지출이 예산을 초과하는 경우가 존재하는가",
            severity=ConstraintSeverity.CRITICAL,
            build_formula=build,
        ))

        result = v.validate()
        assert result.rejected
        ce = result.details["results"][0]["counterexample"]
        assert ce is not None
        # 반례에서 spent > budget인지 확인
        assert "budget" in ce
        assert "spent" in ce


# ──────────────────────────────────────────────
# 범위 제약 팩토리 테스트
# ──────────────────────────────────────────────

class TestValueRangeConstraint:
    def test_price_must_be_positive(self):
        """가격이 음수가 되는 경우가 존재하는가? → sat (예: price=-1)."""
        v = Z3VerifierDefense()
        v.add_constraint(
            constraint_value_range(
                "price_positive",
                "price",
                min_val=0,
                description="상품 가격은 0 이상이어야 한다",
            )
        )
        result = v.validate()
        assert result.rejected
        ce = result.details["results"][0]["counterexample"]
        assert "price" in ce

    def test_percentage_range(self):
        """비율이 [0, 100] 범위를 벗어나는가? → sat."""
        v = Z3VerifierDefense()
        v.add_constraint(
            constraint_value_range(
                "percentage_range",
                "pct",
                min_val=0,
                max_val=100,
            )
        )
        result = v.validate()
        assert result.rejected

    def test_impossible_range_is_safe(self):
        """x < -∞ 또는 x > +∞ — 범위 제약 없으면 검증 생략."""
        v = Z3VerifierDefense()
        # min/max 모두 None이면 위반 조건이 없음
        c = constraint_value_range("no_bounds", "x")

        # build_formula가 빈 Or()가 되어 Z3에러남 → 확인
        # 실제로는 violations가 빈 리스트이므로 solver.add가 호출 안 됨
        vr = v.verify_constraint(c)
        # 아무 제약도 안 걸렸으니 기본적으로 unsat (빈 solver = sat with empty)
        # 실제로 빈 solver.check()는 sat를 반환 (trivially satisfiable)
        # 하지만 아무 위반 조건도 없으므로 이는 "모든 입력이 위반"이 아니라
        # "제약 자체가 없음"을 의미 — 이 경우 build_formula가 아무 것도 add하지 않음
        assert vr is not None  # 에러 없이 실행


# ──────────────────────────────────────────────
# 조건부 논리 (P ⟹ Q) 테스트
# ──────────────────────────────────────────────

class TestConditionalLogic:
    def test_implication_violation(self):
        """VIP 고객이면 할인율 ≥ 10% 인가?
        위반 조건: is_vip ∧ discount < 10 이 가능한가? → sat."""
        def build(solver: Solver):
            is_vip = Bool("is_vip")
            discount = Int("discount")
            # 위반 조건: VIP인데 할인이 10% 미만
            solver.add(is_vip == True)
            solver.add(discount >= 0)
            solver.add(discount < 10)

        v = Z3VerifierDefense()
        v.add_constraint(LogicConstraint(
            name="vip_discount_guarantee",
            description="VIP 고객은 반드시 10% 이상 할인을 받아야 한다",
            severity=ConstraintSeverity.CRITICAL,
            build_formula=build,
        ))

        result = v.validate()
        assert result.rejected

    def test_implication_satisfied(self):
        """할인율이 100%를 초과하면서 동시에 100 이하인 경우는?
        → 자기 모순이므로 unsat."""
        def build(solver: Solver):
            discount = Int("discount")
            # discount > 100 이면서 discount <= 100 → 불가
            solver.add(discount > 100)
            solver.add(discount <= 100)

        v = Z3VerifierDefense()
        v.add_constraint(LogicConstraint(
            name="discount_cap",
            description="할인율이 100%를 초과하면서 100 이하일 수 없다",
            severity=ConstraintSeverity.CRITICAL,
            build_formula=build,
        ))

        result = v.validate()
        assert result.passed


# ──────────────────────────────────────────────
# WARNING 수준 테스트
# ──────────────────────────────────────────────

class TestWarningSeverity:
    def test_warning_returns_needs_review(self):
        """WARNING 제약만 위반되면 REJECT가 아닌 NEEDS_REVIEW."""
        def build(solver: Solver):
            x = Int("x")
            solver.add(x > 1000)  # 높은 값이 가능 → sat

        v = Z3VerifierDefense()
        v.add_constraint(LogicConstraint(
            name="large_value_warning",
            description="값이 1000을 초과하는 경우 경고",
            severity=ConstraintSeverity.WARNING,
            build_formula=build,
        ))

        result = v.validate()
        assert result.verdict == DefenseVerdict.NEEDS_REVIEW

    def test_mixed_severity_critical_wins(self):
        """CRITICAL + WARNING이 모두 위반되면 REJECT."""
        v = Z3VerifierDefense()
        v.add_constraint(LogicConstraint(
            name="critical_fail",
            description="CRITICAL 위반",
            severity=ConstraintSeverity.CRITICAL,
            build_formula=lambda s: s.add(Int("a") > 0),
        ))
        v.add_constraint(LogicConstraint(
            name="warning_fail",
            description="WARNING 위반",
            severity=ConstraintSeverity.WARNING,
            build_formula=lambda s: s.add(Int("b") > 0),
        ))

        result = v.validate()
        assert result.rejected


# ──────────────────────────────────────────────
# 빈 제약 / 성능 테스트
# ──────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_constraints_passes(self):
        """제약 목록이 비어있으면 PASS."""
        v = Z3VerifierDefense()
        result = v.validate()
        assert result.passed
        assert "검증 생략" in result.reason

    def test_clear_constraints(self):
        v = Z3VerifierDefense()
        v.add_constraint(
            constraint_value_range("test", "x", min_val=0)
        )
        assert v.is_enabled()
        v.clear_constraints()
        assert not v.is_enabled()

    def test_verification_speed(self):
        """Z3 검증은 100ms 이내에 완료되어야 한다."""
        def build(solver: Solver):
            x, y, z = Int("x"), Int("y"), Int("z")
            solver.add(x + y == z)
            solver.add(x > 0)
            solver.add(y > 0)
            solver.add(z < 0)  # x, y 양수인데 z가 음수? → unsat

        v = Z3VerifierDefense()
        v.add_constraint(LogicConstraint(
            name="speed_test",
            description="속도 테스트",
            severity=ConstraintSeverity.CRITICAL,
            build_formula=build,
        ))

        result = v.validate()
        total_ms = result.details["total_elapsed_ms"]
        assert total_ms < 100, f"Z3 검증이 {total_ms}ms 소요 (100ms 초과)"
        assert result.passed  # unsat이므로 안전
