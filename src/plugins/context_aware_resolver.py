# src/plugins/context_aware_resolver.py ('진화'된 v4 코드)

from __future__ import annotations

import pathlib
import shutil # '진화': 폴더 초기화(rmtree)를 위해 임포트
from typing import Dict, Any, List, Set

from denavy_common import BasePlugin, CycleState, PluginResult
from plugins.registry import register_plugin


class ContextCollectorPlugin(BasePlugin):
    name = "context_collector"
    description = "파일, 폴더, glob 패턴을 기반으로 파일 컨텍스트를 수집, 결합, 또는 개별 .md로 저장합니다."

    def _read_and_append(self, path: pathlib.Path, base_path: pathlib.Path, combined_content: List[str], format_mode: str) -> None:
        # (v3와 동일 - 'single_string' 또는 'markdown' 모드에서 사용됨)
        try:
            content = path.read_text(encoding='utf-8')
            relative_path = path.relative_to(base_path).as_posix()
            
            if format_mode == "markdown":
                file_type = path.suffix.lstrip('.') or "text"
                combined_content.append(f"## `{relative_path}`\n")
                combined_content.append(f"```{file_type}\n{content}\n```\n")
            else:
                combined_content.append(f"=== {relative_path} ===\n{content}\n")
                
        except Exception as e:
            relative_path = path.relative_to(base_path).as_posix()
            combined_content.append(f"## `{relative_path}` (ERROR)\n\n```text\nFailed to read: {str(e)}\n```\n")

    # '진화': v4 'flat_md' 모드를 위한 새 헬퍼 함수
    def _write_individual_md(self, path: pathlib.Path, base_path: pathlib.Path, output_dir: pathlib.Path) -> None:
        """
        단일 파일을 읽어, 경로가 인코딩된 .md 파일로 'output_dir'에 저장합니다.
        (예: 'src/core/engine.py' -> 'outputs/src_core_engine.py.md')
        """
        try:
            content = path.read_text(encoding='utf-8')
            relative_path = path.relative_to(base_path).as_posix()
            
            # '진화': 파일 이름 인코딩 (범규님 아이디어)
            # 'src/denavy_common/contracts.py' -> 'src_denavy_common_contracts.py'
            safe_name = relative_path.replace("/", "_").replace("\\", "_")
            output_filename = f"{safe_name}.md" # .md 확장자 추가
            output_path = output_dir / output_filename

            # '진화': 개별 .md 파일 생성
            file_type = path.suffix.lstrip('.') or "text"
            md_content = f"# `{relative_path}`\n\n```{file_type}\n{content}\n```\n"
            
            output_path.write_text(md_content, encoding='utf-8')

        except Exception as e:
            print(f"[WARN] Failed to export {path.name}: {e}")

    def run(self, state: CycleState, config: Dict[str, Any]) -> PluginResult:
        
        base_path = pathlib.Path(config.get("base_path", "."))
        
        # '진화': v4 모드 설정 읽기
        # 'single_string' (v1), 'markdown' (v3), 'flat_md' (v4)
        export_mode = config.get("export_mode", "markdown") 
        output_dir_str = config.get("output_dir", "outputs/notebooklm_export")
        output_dir = pathlib.Path(output_dir_str)

        # (파일 수집 로직은 동일) ...
        user_configured_collection = (
            "directories" in config or
            "files" in config or
            "include_patterns" in config
        )
        directories: List[str] = config.get("directories", [])
        files: List[str] = config.get("files", [])
        include_patterns: List[str] = config.get("include_patterns", [])
        default_exclude = [
            "**/__pycache__/**", "**/.git/**", "**/node_modules/**",
            "**/.venv/**", "**/*.pyc", "**/*.pyo", "**/*.egg-info/**", ".env",
            "logs/**", "outputs/**"
        ]
        exclude_patterns: List[str] = config.get("exclude_patterns", default_exclude)
        files_to_read: Set[pathlib.Path] = set()
        for dir_name in directories:
            dir_path = base_path / dir_name
            if dir_path.is_dir():
                for path in dir_path.rglob('*'):
                    if path.is_file():
                        files_to_read.add(path)
        for file_name in files:
            file_path = base_path / file_name
            if file_path.is_file():
                files_to_read.add(file_path)
        if not user_configured_collection:
            include_patterns = ["**/*"]
        for pattern in include_patterns:
            for path in base_path.glob(pattern):
                if path.is_file():
                    files_to_read.add(path)
        excluded_files: Set[pathlib.Path] = set()
        for pattern in exclude_patterns:
            for path in base_path.glob(pattern):
                if path.is_file():
                    excluded_files.add(path)
        final_files_to_read = sorted(list(files_to_read - excluded_files))
        # ... (파일 수집 로직 끝)

        # '진화': v4 모드 분기
        if export_mode == "flat_md":
            # === v4 '개별 .md 파일' 모드 ===
            if output_dir.exists():
                shutil.rmtree(output_dir) # 기존 '산출물' 폴더 초기화
            output_dir.mkdir(parents=True, exist_ok=True)

            for path in final_files_to_read:
                self._write_individual_md(path, base_path, output_dir)
            
            message = f"Successfully exported {len(final_files_to_read)} files to '{output_dir_str}'"
            return PluginResult(status="success", message=message, output={"output_dir": output_dir_str})
        
        else:
            # === v1/v3 '단일 결합' 모드 ===
            combined_content = []
            for path in final_files_to_read:
                self._read_and_append(path, base_path, combined_content, export_mode)
            
            file_contents = "\n".join(combined_content)
            message = f"Successfully read and combined {len(final_files_to_read)} file(s)"
            
            return PluginResult(
                status="success",
                output={"file_contents": file_contents},
                file_contents=file_contents,
                message=message,
            )
    
register_plugin(ContextCollectorPlugin)
