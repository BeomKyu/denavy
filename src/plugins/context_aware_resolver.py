from __future__ import annotations

import pathlib
from typing import Dict, Any, List, Set

from denavy_common import BasePlugin, CycleState, PluginResult
from plugins.registry import register_plugin


class ContextCollectorPlugin(BasePlugin):
    """
    강력한 포함/제외 패턴을 사용하여 파일 시스템에서 컨텍스트를 수집하는
    단일 통합 플러그인입니다.
    """

    name = "context_collector"
    description = "파일, 폴더, glob 패턴을 기반으로 파일 컨텍스트를 수집합니다."

    def _read_and_append(self, path: pathlib.Path, base_path: pathlib.Path, combined_content: List[str]) -> None:
        """파일을 읽고 combined_content 리스트에 추가합니다."""
        try:
            content = path.read_text(encoding='utf-8')
            # base_path 기준 상대 경로 사용
            relative_path = path.relative_to(base_path)
            combined_content.append(f"=== {relative_path} ===\n{content}\n")
        except Exception as e:
            relative_path = path.relative_to(base_path)
            combined_content.append(f"=== {relative_path} (ERROR) ===\nFailed to read: {str(e)}\n")

    def run(self, state: CycleState, config: Dict[str, Any]) -> PluginResult:
        """
        'config'에서 'base_path', 'directories', 'files', 'include_patterns', 
        'exclude_patterns'를 읽어 파일 내용을 결합합니다.
        """
        
        # 1. 설정값 읽기
        base_path = pathlib.Path(config.get("base_path", "."))
        
        # 사용자가 요청한 특정 폴더, 파일, 포함 패턴
        directories: List[str] = config.get("directories", [])
        files: List[str] = config.get("files", [])
        include_patterns: List[str] = config.get("include_patterns", [])
        
        # 제외할 패턴 목록 (기본값: 일반적인 제외 목록)
        default_exclude = [
            "**/__pycache__/**", "**/.git/**", "**/node_modules/**",
            "**/.venv/**", "**/*.pyc", "**/*.pyo", "**/*.egg-info/**", ".env"
        ]
        exclude_patterns: List[str] = config.get("exclude_patterns", default_exclude)

        # 2. 다양한 소스에서 파일 수집 (중복 제거를 위해 Set 사용)
        files_to_read: Set[pathlib.Path] = set()

        # 2a. 'directories' (폴더 목록) 처리: 하위 모든 파일 재귀 탐색
        for dir_name in directories:
            dir_path = base_path / dir_name
            if dir_path.is_dir():
                for path in dir_path.rglob('*'):
                    if path.is_file():
                        files_to_read.add(path)

        # 2b. 'files' (파일 목록) 처리
        for file_name in files:
            file_path = base_path / file_name
            if file_path.is_file():
                files_to_read.add(file_path)

        # 2c. 'include_patterns' (Glob 패턴) 처리
        # 만약 위 3가지가 모두 비어있다면, '모두'를 의미하도록 **/*를 기본값으로 사용
        if not directories and not files and not include_patterns:
            include_patterns = ["**/*"]
            
        for pattern in include_patterns:
            for path in base_path.glob(pattern):
                if path.is_file():
                    files_to_read.add(path)

        # 3. 제외(exclude) 패턴 처리
        excluded_files: Set[pathlib.Path] = set()
        for pattern in exclude_patterns:
            for path in base_path.glob(pattern):
                if path.is_file():
                    excluded_files.add(path)

        # 포함된 파일에서 제외된 파일을 뺍니다.
        final_files_to_read = sorted(list(files_to_read - excluded_files))

        # 4. 파일 내용 읽기
        combined_content = []
        for path in final_files_to_read:
            self._read_and_append(path, base_path, combined_content)
        
        file_contents = "\n".join(combined_content)
        message = f"Successfully read {len(final_files_to_read)} file(s) from '{base_path}'"
        
        return PluginResult(
            status="success",
            output={"file_contents": file_contents},
            state_updates={"file_contents": file_contents},
            message=message,
        )
    
register_plugin(ContextCollectorPlugin)
