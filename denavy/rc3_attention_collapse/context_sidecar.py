"""
RC3: CQRS 컨텍스트 사이드카 — 구체화된 뷰(Materialized View) 투영
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
근본 원인 3 — 어텐션 기하학적 붕괴
  (Attention Geometry Collapse)

억압 결함:
  결함 3 — 단기 기억 상실: 트랜스포머 중간 유실(Lost-in-the-Middle)
  결함 4 — 토큰 경제 파괴: 불필요한 코드를 맹목적으로 Context에 투입
  결함 5 — 컨텍스트 폭주: 과부하로 기존 코드를 통째로 덮어쓰기

핵심 원리:
  에이전트를 완벽한 무상태(Stateless)로 설계한다.
  매 턴마다 전체 코드를 맹목적으로 밀어넣는 대신,
  CQRS(Command Query Responsibility Segregation) 패턴으로
  "현재 작업에 정확히 필요한 코드 슬라이스"만 추출하여
  구체화된 뷰(Materialized View)로 투영한다.

  → 토큰 사용량 최소화
  → 어텐션 중간 유실 방지 (필요한 것만 근거리에 배치)
  → 과부하 제거 (전체 코드 대신 슬라이스만 전달)
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from denavy.protocols import DefenseResult, DefenseVerdict, RootCauseDefense

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 코드 슬라이스 데이터 모델
# ──────────────────────────────────────────────

@dataclass(frozen=True)
class CodeSlice:
    """코드베이스의 최소 단위 슬라이스.

    전체 파일이 아닌, 작업에 필요한 함수/클래스/블록 단위.
    """
    file_path: str
    symbol_name: str      # 함수/클래스 이름
    symbol_type: str      # "function", "class", "module"
    start_line: int
    end_line: int
    source: str           # 해당 영역의 소스 코드
    dependencies: list[str] = field(default_factory=list)  # import 목록


@dataclass
class MaterializedView:
    """에이전트에게 전달할 구체화된 뷰.

    전체 코드가 아닌, 작업에 필요한 슬라이스들의 조합.
    """
    task_id: str
    target_file: str
    slices: list[CodeSlice] = field(default_factory=list)
    total_tokens_estimate: int = 0   # 대략적 토큰 수 (chars / 4)
    context_ratio: float = 0.0       # 전체 대비 투영 비율

    @property
    def total_lines(self) -> int:
        return sum(s.end_line - s.start_line + 1 for s in self.slices)


# ──────────────────────────────────────────────
# 코드 인덱서 — 파일에서 심볼 추출
# ──────────────────────────────────────────────

class CodeIndexer:
    """Python 소스 파일에서 함수/클래스 심볼을 추출하여 인덱싱한다.

    전체 코드를 한 덩어리로 전달하는 대신,
    심볼 단위로 분리하여 필요한 것만 선택적으로 투영.
    """

    def __init__(self, project_root: str | Path) -> None:
        self._root = Path(project_root)
        self._index: dict[str, list[CodeSlice]] = {}  # file_path → slices

    @staticmethod
    def _normalize(path: str | Path) -> str:
        """경로를 POSIX 형식으로 정규화 (Windows 호환)."""
        return str(path).replace("\\", "/")

    def index_file(self, file_path: str | Path) -> list[CodeSlice]:
        """단일 파일을 인덱싱하여 심볼 슬라이스 목록을 반환한다."""
        norm_path = self._normalize(file_path)
        abs_path = self._root / norm_path
        if not abs_path.exists():
            return []

        try:
            source = abs_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"RC3: 파일 읽기 실패 {norm_path}: {e}")
            return []

        slices = self._extract_symbols(norm_path, source)
        self._index[norm_path] = slices
        return slices

    def index_project(
        self, extensions: tuple[str, ...] = (".py",)
    ) -> dict[str, list[CodeSlice]]:
        """프로젝트 전체를 재귀적으로 인덱싱한다."""
        for py_file in self._root.rglob("*"):
            if py_file.suffix in extensions and py_file.is_file():
                rel = py_file.relative_to(self._root)
                self.index_file(self._normalize(rel))
        return self._index

    def get_slices(self, file_path: str) -> list[CodeSlice]:
        """인덱싱된 파일의 슬라이스 목록을 반환한다."""
        return self._index.get(self._normalize(file_path), [])

    def find_symbol(
        self, symbol_name: str, file_path: str | None = None
    ) -> list[CodeSlice]:
        """이름으로 심볼을 검색한다."""
        results = []
        if file_path:
            norm = self._normalize(file_path)
            search_scope = {norm: self._index.get(norm, [])}
        else:
            search_scope = self._index
        for path, slices in search_scope.items():
            for s in slices:
                if s.symbol_name == symbol_name:
                    results.append(s)
        return results

    def _extract_symbols(
        self, file_path: str, source: str
    ) -> list[CodeSlice]:
        """AST로 소스에서 함수/클래스 심볼을 추출한다."""
        try:
            tree = ast.parse(source, filename=file_path)
        except SyntaxError:
            # 파싱 불가 → 전체 파일을 하나의 슬라이스로
            lines = source.split("\n")
            return [CodeSlice(
                file_path=file_path,
                symbol_name="<module>",
                symbol_type="module",
                start_line=1,
                end_line=len(lines),
                source=source,
            )]

        slices: list[CodeSlice] = []
        lines = source.split("\n")

        # import 목록 추출
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)

        # 최상위 함수/클래스 추출
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                start = node.lineno
                end = node.end_lineno or node.lineno
                slices.append(CodeSlice(
                    file_path=file_path,
                    symbol_name=node.name,
                    symbol_type="function",
                    start_line=start,
                    end_line=end,
                    source="\n".join(lines[start - 1 : end]),
                    dependencies=imports,
                ))

            elif isinstance(node, ast.ClassDef):
                start = node.lineno
                end = node.end_lineno or node.lineno
                slices.append(CodeSlice(
                    file_path=file_path,
                    symbol_name=node.name,
                    symbol_type="class",
                    start_line=start,
                    end_line=end,
                    source="\n".join(lines[start - 1 : end]),
                    dependencies=imports,
                ))

        return slices

    @property
    def indexed_files(self) -> list[str]:
        return list(self._index.keys())


# ──────────────────────────────────────────────
# 뷰 빌더 — 구체화된 뷰 생성
# ──────────────────────────────────────────────

class ViewBuilder:
    """작업에 필요한 코드 슬라이스를 선택하여 구체화된 뷰를 생성한다.

    전체 코드를 에이전트에게 던져주는 대신:
      1. 대상 파일의 심볼만 추출
      2. 의존성(import)이 참조하는 외부 심볼 추가
      3. 토큰 예산 내에서 뷰를 조립
    """

    def __init__(
        self,
        indexer: CodeIndexer,
        max_tokens: int = 8000,
    ) -> None:
        self._indexer = indexer
        self._max_tokens = max_tokens

    def build_view(
        self,
        task_id: str,
        target_file: str,
        target_symbols: list[str] | None = None,
    ) -> MaterializedView:
        """작업에 필요한 구체화된 뷰를 생성한다.

        Args:
            task_id: 작업 ID
            target_file: 대상 파일 경로
            target_symbols: 필요한 심볼 이름 목록 (None이면 전체)

        Returns:
            MaterializedView: 투영된 코드 슬라이스 뷰
        """
        all_slices = self._indexer.get_slices(target_file)
        if not all_slices:
            # 인덱싱 안 된 파일 → 새로 인덱싱
            all_slices = self._indexer.index_file(target_file)

        # 대상 심볼 필터링
        if target_symbols:
            selected = [
                s for s in all_slices
                if s.symbol_name in target_symbols
            ]
        else:
            selected = list(all_slices)

        # 토큰 예산 내에서 슬라이스 선택
        final_slices: list[CodeSlice] = []
        total_chars = 0
        for sl in selected:
            char_count = len(sl.source)
            if total_chars + char_count > self._max_tokens * 4:
                # 토큰 예산 초과 → 중단
                break
            final_slices.append(sl)
            total_chars += char_count

        # 전체 파일 크기 대비 투영 비율 계산
        total_file_chars = sum(len(s.source) for s in all_slices)
        ratio = total_chars / total_file_chars if total_file_chars > 0 else 0.0

        return MaterializedView(
            task_id=task_id,
            target_file=target_file,
            slices=final_slices,
            total_tokens_estimate=total_chars // 4,
            context_ratio=round(ratio, 3),
        )


# ──────────────────────────────────────────────
# RC3 방어 모듈
# ──────────────────────────────────────────────

class ContextSidecarDefense:
    """RC3: CQRS 컨텍스트 사이드카 방어 모듈.

    에이전트의 컨텍스트 투입량을 검증하고 제한한다.

    이 모듈은 RootCauseDefense Protocol을 구현한다.

    검증 항목:
      1. 맹목적 전체 파일 투입 감지 (context_ratio > threshold)
      2. 토큰 예산 초과 감지
      3. 구체화된 뷰 없이 원시 코드 투입 시도 차단
    """

    def __init__(
        self,
        max_tokens_per_request: int = 8000,
        max_context_ratio: float = 0.8,
    ) -> None:
        self._max_tokens = max_tokens_per_request
        self._max_ratio = max_context_ratio

    @property
    def root_cause_id(self) -> int:
        return 3

    @property
    def target_defects(self) -> list[int]:
        return [3, 4, 5]

    def is_enabled(self) -> bool:
        return True

    def validate(self, input_data: Any) -> DefenseResult:
        """컨텍스트 투입량을 검증한다.

        Args:
            input_data: 다음 중 하나:
              - MaterializedView: 구체화된 뷰 (정상 경로)
              - dict: {"raw_code": str} (맹목적 투입 시도)
              - str: 원시 코드 문자열

        Returns:
            DefenseResult: 검증 결과
        """
        if isinstance(input_data, MaterializedView):
            return self._validate_view(input_data)

        if isinstance(input_data, dict) and "raw_code" in input_data:
            raw = input_data["raw_code"]
            estimated_tokens = len(raw) // 4
            if estimated_tokens > self._max_tokens:
                return DefenseResult(
                    verdict=DefenseVerdict.REJECT,
                    module_name="RC3_ContextSidecar",
                    root_cause_id=3,
                    reason=(
                        f"원시 코드 맹목 투입: ~{estimated_tokens} 토큰 "
                        f"(상한 {self._max_tokens}). "
                        "구체화된 뷰(MaterializedView)를 사용하세요."
                    ),
                    details={"estimated_tokens": estimated_tokens},
                )

        if isinstance(input_data, str):
            estimated_tokens = len(input_data) // 4
            if estimated_tokens > self._max_tokens:
                return DefenseResult(
                    verdict=DefenseVerdict.REJECT,
                    module_name="RC3_ContextSidecar",
                    root_cause_id=3,
                    reason=(
                        f"원시 문자열 토큰 초과: ~{estimated_tokens} 토큰 "
                        f"(상한 {self._max_tokens})"
                    ),
                    details={"estimated_tokens": estimated_tokens},
                )

        return DefenseResult(
            verdict=DefenseVerdict.PASS,
            module_name="RC3_ContextSidecar",
            root_cause_id=3,
            reason="컨텍스트 검증 통과",
        )

    def _validate_view(self, view: MaterializedView) -> DefenseResult:
        """구체화된 뷰의 효율성을 검증한다."""
        issues = []

        # 토큰 예산 초과
        if view.total_tokens_estimate > self._max_tokens:
            issues.append(
                f"토큰 예산 초과: {view.total_tokens_estimate} "
                f"(상한 {self._max_tokens})"
            )

        # 전체 코드 비율 임계값 초과 (거의 전체를 투입)
        if view.context_ratio > self._max_ratio:
            issues.append(
                f"컨텍스트 비율 {view.context_ratio:.1%} "
                f"(임계값 {self._max_ratio:.1%}) — "
                "파일 전체를 투입하고 있습니다. 슬라이스를 줄이세요."
            )

        if issues:
            return DefenseResult(
                verdict=DefenseVerdict.NEEDS_REVIEW,
                module_name="RC3_ContextSidecar",
                root_cause_id=3,
                reason=f"컨텍스트 효율성 경고: {issues[0]}",
                details={
                    "issues": issues,
                    "tokens": view.total_tokens_estimate,
                    "ratio": view.context_ratio,
                    "slices_count": len(view.slices),
                },
            )

        return DefenseResult(
            verdict=DefenseVerdict.PASS,
            module_name="RC3_ContextSidecar",
            root_cause_id=3,
            reason=(
                f"구체화된 뷰 검증 통과 "
                f"({len(view.slices)}개 슬라이스, "
                f"~{view.total_tokens_estimate} 토큰, "
                f"비율 {view.context_ratio:.1%})"
            ),
        )
