"""
RC2-B: AST 기반 구조적 코드 분석 모듈
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
근본 원인 2 — 자기회귀 노출 편향

억압 결함:
  결함 11 — 의미론적 표류 (아키텍처 경계 침범, 모듈 간 암묵적 결합)

핵심 원리:
  에이전트가 생성한 코드가 파이선 AST로 파싱 가능한지,
  그리고 아키텍처 규칙을 위반하지 않는지 기계적으로 검사한다.
  - 파싱 불가 코드 → 즉각 거부
  - 금지된 import → 모듈 경계 침범 감지
  - 과도한 함수/클래스 수 → 단일 파일 밀어넣기 감지
  - 과도한 함수 길이 → 스파게티 코드 감지
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from typing import Any

from denavy.protocols import DefenseResult, DefenseVerdict

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# AST 분석 결과
# ──────────────────────────────────────────────

@dataclass
class ASTAnalysis:
    """코드의 AST 분석 결과."""
    parseable: bool = True
    parse_error: str = ""

    # 구조 메트릭
    num_functions: int = 0
    num_classes: int = 0
    num_imports: int = 0
    max_function_lines: int = 0
    total_lines: int = 0
    imported_modules: list[str] = field(default_factory=list)

    # 위반 목록
    violations: list[str] = field(default_factory=list)


# ──────────────────────────────────────────────
# AST 코드 분석기
# ──────────────────────────────────────────────

class ASTCodeAnalyzer:
    """Python 코드의 구조적 건전성을 AST로 분석한다.

    분석 항목:
      - 파싱 가능 여부
      - 함수/클래스 수 (단일 파일 밀어넣기 감지)
      - 최대 함수 길이 (스파게티 코드 감지)
      - import 목록 (모듈 경계 침범 감지)
    """

    def __init__(
        self,
        max_functions_per_file: int = 30,
        max_classes_per_file: int = 10,
        max_function_lines: int = 100,
        forbidden_imports: list[str] | None = None,
    ) -> None:
        """
        Args:
            max_functions_per_file: 파일당 최대 함수 수
            max_classes_per_file: 파일당 최대 클래스 수
            max_function_lines: 함수당 최대 줄 수
            forbidden_imports: 금지된 import 패턴 목록
        """
        self._max_functions = max_functions_per_file
        self._max_classes = max_classes_per_file
        self._max_function_lines = max_function_lines
        self._forbidden_imports = forbidden_imports or []

    # Protocol 호환 프로퍼티
    @property
    def root_cause_id(self) -> int:
        return 2

    @property
    def target_defects(self) -> list[int]:
        return [11]

    def is_enabled(self) -> bool:
        return True

    def validate(self, input_data: Any) -> DefenseResult:
        """RootCauseDefense Protocol 호환 validate.

        input_data가 str이면 코드로 직접 검증,
        dict이면 code_changes에서 코드 추출.
        """
        if isinstance(input_data, str):
            return self.validate_code(input_data)
        if isinstance(input_data, dict):
            code = input_data.get("code", "")
            if not code:
                changes = input_data.get("code_changes", [])
                if changes:
                    code = "\n".join(
                        c.get("new_content", "") for c in changes if c.get("new_content")
                    )
            return self.validate_code(code or "pass")
        return self.validate_code("pass")

    def analyze(self, code: str, filename: str = "<agent>") -> ASTAnalysis:
        """Python 코드를 AST로 분석한다.

        Args:
            code: 분석할 Python 소스 코드
            filename: 파일명 (에러 메시지용)

        Returns:
            ASTAnalysis: 분석 결과
        """
        result = ASTAnalysis(total_lines=code.count("\n") + 1)

        # 1. 파싱 가능 여부
        try:
            tree = ast.parse(code, filename=filename)
        except SyntaxError as e:
            result.parseable = False
            result.parse_error = f"구문 오류({filename}:{e.lineno}): {e.msg}"
            result.violations.append(result.parse_error)
            return result

        # 2. 최상위 노드 순회
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                result.num_functions += 1
                func_lines = (node.end_lineno or 0) - (node.lineno or 0) + 1
                result.max_function_lines = max(
                    result.max_function_lines, func_lines
                )

                # 함수 길이 위반
                if func_lines > self._max_function_lines:
                    result.violations.append(
                        f"함수 '{node.name}'이 {func_lines}줄 "
                        f"(상한 {self._max_function_lines}줄)"
                    )

            elif isinstance(node, ast.ClassDef):
                result.num_classes += 1

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    result.num_imports += 1
                    result.imported_modules.append(alias.name)

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    result.num_imports += 1
                    result.imported_modules.append(node.module)

        # 3. 밀어넣기 감지
        if result.num_functions > self._max_functions:
            result.violations.append(
                f"파일에 {result.num_functions}개 함수 "
                f"(상한 {self._max_functions}개 — 단일파일 밀어넣기 의심)"
            )

        if result.num_classes > self._max_classes:
            result.violations.append(
                f"파일에 {result.num_classes}개 클래스 "
                f"(상한 {self._max_classes}개 — 단일파일 밀어넣기 의심)"
            )

        # 4. 금지된 import 검사
        for mod in result.imported_modules:
            for forbidden in self._forbidden_imports:
                if mod == forbidden or mod.startswith(forbidden + "."):
                    result.violations.append(
                        f"금지된 모듈 import: '{mod}' "
                        f"(매칭: '{forbidden}')"
                    )

        return result

    def validate_code(self, code: str, filename: str = "<agent>") -> DefenseResult:
        """코드를 분석하고 DefenseResult를 반환한다.

        Args:
            code: 검증할 Python 소스 코드
            filename: 파일명

        Returns:
            DefenseResult: PASS이면 구조적으로 건전, REJECT이면 위반 발견
        """
        analysis = self.analyze(code, filename)

        if not analysis.parseable:
            return DefenseResult(
                verdict=DefenseVerdict.REJECT,
                module_name="RC2_ASTParser",
                root_cause_id=2,
                reason=f"파싱 불가: {analysis.parse_error}",
                details={"analysis": self._analysis_to_dict(analysis)},
            )

        if analysis.violations:
            return DefenseResult(
                verdict=DefenseVerdict.REJECT,
                module_name="RC2_ASTParser",
                root_cause_id=2,
                reason=(
                    f"코드 구조 위반 {len(analysis.violations)}건: "
                    f"{analysis.violations[0]}"
                ),
                details={"analysis": self._analysis_to_dict(analysis)},
            )

        return DefenseResult(
            verdict=DefenseVerdict.PASS,
            module_name="RC2_ASTParser",
            root_cause_id=2,
            reason=(
                f"AST 구조 검증 통과 "
                f"(함수 {analysis.num_functions}개, "
                f"클래스 {analysis.num_classes}개, "
                f"최대 함수길이 {analysis.max_function_lines}줄)"
            ),
            details={"analysis": self._analysis_to_dict(analysis)},
        )

    @staticmethod
    def _analysis_to_dict(a: ASTAnalysis) -> dict[str, Any]:
        return {
            "parseable": a.parseable,
            "parse_error": a.parse_error,
            "num_functions": a.num_functions,
            "num_classes": a.num_classes,
            "num_imports": a.num_imports,
            "max_function_lines": a.max_function_lines,
            "total_lines": a.total_lines,
            "violations": a.violations,
        }
