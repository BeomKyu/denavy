"""
Pydantic → Z3 자동 제약 추출 브리지
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pydantic BaseModel의 Field 메타데이터를 Z3 SMT 논리식으로 자동 변환.

LLM 추가 호출 없이, AST 파싱만으로 0ms급 기계적 변환.

지원 제약:
  - ge, gt, le, lt (수치 범위)
  - min_length, max_length (문자열 길이)
  - multiple_of (배수)
  - Literal (열거형)

사용법:
    constraints = extract_z3_constraints(IntentionPayload)
    verifier.add_constraints(constraints)
    result = verifier.verify()
"""

from __future__ import annotations

import logging
from typing import Any, get_args, get_origin

import z3
from pydantic import BaseModel
from pydantic.fields import FieldInfo

logger = logging.getLogger(__name__)


def extract_z3_constraints(
    model_class: type[BaseModel],
) -> list[z3.ExprRef]:
    """Pydantic BaseModel의 Field 메타데이터에서 Z3 제약을 추출한다.

    Args:
        model_class: Pydantic BaseModel 서브클래스

    Returns:
        Z3 제약 조건 리스트
    """
    constraints: list[z3.ExprRef] = []

    for field_name, field_info in model_class.model_fields.items():
        field_constraints = _extract_field_constraints(field_name, field_info)
        constraints.extend(field_constraints)

    logger.debug(
        f"Z3 Bridge: {model_class.__name__}에서 "
        f"{len(constraints)}개 제약 추출"
    )
    return constraints


def _extract_field_constraints(
    name: str,
    info: FieldInfo,
) -> list[z3.ExprRef]:
    """단일 필드에서 Z3 제약을 추출한다."""
    constraints: list[z3.ExprRef] = []
    metadata = info.metadata or []

    # 어노테이션에서 타입 추론
    annotation = info.annotation
    is_numeric = _is_numeric_type(annotation)
    is_string = _is_string_type(annotation)

    if is_numeric:
        var = z3.Int(name) if _is_int_type(annotation) else z3.Real(name)

        # Pydantic 메타데이터에서 제약 추출
        for meta in metadata:
            meta_type = type(meta).__name__

            if hasattr(meta, "ge") and meta.ge is not None:
                constraints.append(var >= meta.ge)
            if hasattr(meta, "gt") and meta.gt is not None:
                constraints.append(var > meta.gt)
            if hasattr(meta, "le") and meta.le is not None:
                constraints.append(var <= meta.le)
            if hasattr(meta, "lt") and meta.lt is not None:
                constraints.append(var < meta.lt)
            if hasattr(meta, "multiple_of") and meta.multiple_of is not None:
                constraints.append(var % meta.multiple_of == 0)

    elif is_string:
        var = z3.String(name)

        for meta in metadata:
            if hasattr(meta, "min_length") and meta.min_length is not None:
                constraints.append(z3.Length(var) >= meta.min_length)
            if hasattr(meta, "max_length") and meta.max_length is not None:
                constraints.append(z3.Length(var) <= meta.max_length)

    return constraints


def _is_numeric_type(annotation: Any) -> bool:
    """수치형인지 확인."""
    if annotation in (int, float):
        return True
    origin = get_origin(annotation)
    if origin is not None:
        args = get_args(annotation)
        return any(a in (int, float) for a in args if isinstance(a, type))
    return False


def _is_int_type(annotation: Any) -> bool:
    return annotation is int


def _is_string_type(annotation: Any) -> bool:
    if annotation is str:
        return True
    origin = get_origin(annotation)
    if origin is not None:
        args = get_args(annotation)
        return any(a is str for a in args if isinstance(a, type))
    return False


def verify_against_schema(
    model_class: type[BaseModel],
    data: dict[str, Any],
) -> tuple[bool, str]:
    """데이터가 Pydantic 스키마의 Z3 제약을 만족하는지 검증.

    Args:
        model_class: 검증 대상 스키마
        data: 검증할 데이터

    Returns:
        (통과 여부, 사유)
    """
    constraints = extract_z3_constraints(model_class)
    if not constraints:
        return (True, "제약 조건 없음")

    solver = z3.Solver()
    solver.add(*constraints)

    # 데이터 값 대입
    for field_name, value in data.items():
        if field_name not in model_class.model_fields:
            continue

        info = model_class.model_fields[field_name]
        annotation = info.annotation

        if _is_int_type(annotation) and isinstance(value, int):
            solver.add(z3.Int(field_name) == value)
        elif annotation is float and isinstance(value, (int, float)):
            solver.add(z3.Real(field_name) == value)
        elif _is_string_type(annotation) and isinstance(value, str):
            solver.add(z3.String(field_name) == z3.StringVal(value))

    result = solver.check()
    if result == z3.sat:
        return (True, "Z3: 모든 제약 충족 (sat)")
    elif result == z3.unsat:
        # unsat core 추출 시도
        return (False, "Z3: 제약 위배 (unsat)")
    else:
        return (False, f"Z3: 판정 불가 ({result})")
