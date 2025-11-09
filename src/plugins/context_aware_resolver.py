from denavy_common import BasePlugin, CycleState, PluginResult
import pathlib
from typing import Dict, Any, List

class DirectoryReaderPlugin(BasePlugin):
    """디렉토리 내 모든 파일을 재귀적으로 읽어 내용을 결합하는 플러그인"""
    
    name = "context_aware_resolver"
    description = "지정된 디렉토리의 모든 파일을 재귀적으로 읽어 내용을 결합합니다"

    def _should_exclude(self, path: pathlib.Path, base_path: pathlib.Path, 
                        exclude_dirs: List[str], exclude_patterns: List[str]) -> bool:
        """경로가 제외 대상인지 확인합니다."""
        relative_path = path.relative_to(base_path)
        path_parts = relative_path.parts
        
        # 제외할 디렉토리 확인
        for part in path_parts:
            if part in exclude_dirs:
                return True
        
        # 제외할 패턴 확인
        path_str = str(relative_path)
        for pattern in exclude_patterns:
            if pattern in path_str:
                return True
        
        return False
    
    
    def run(self, state: CycleState, config: Dict[str, Any]) -> PluginResult:
        """설정된 디렉토리의 모든 파일을 재귀적으로 읽어 내용을 결합합니다."""
        directory = config.get("directory", ".")

        exclude_dirs = config.get("exclude_dirs", ["__pycache__", ".git", "node_modules", ".venv", "venv"])
        exclude_patterns = config.get("exclude_patterns", [".pyc", ".pyo", ".egg-info"])

        combined_content = []
        base_path = pathlib.Path(directory)
        
        # 디렉토리 내 모든 파일을 재귀적으로 탐색
        file_count = 0
        excluded_count = 0

        for path in base_path.rglob('*'):
            # 디렉토리가 아닌 파일만 처리
            # 제외 대상 확인
            if self._should_exclude(path, base_path, exclude_dirs, exclude_patterns):
                excluded_count += 1
                continue

            if not path.is_dir():
                try:
                    content = path.read_text(encoding='utf-8')
                    relative_path = path.relative_to(base_path)
                    combined_content.append(f"=== {relative_path} ===\n{content}\n")
                    file_count += 1
                except Exception as e:
                    relative_path = path.relative_to(base_path)
                    combined_content.append(f"=== {relative_path} (ERROR) ===\nFailed to read: {str(e)}\n")
        
        file_contents = "\n".join(combined_content)
        
        return PluginResult(
            status="success",
            output={"file_contents": file_contents},
            state_updates={"file_contents": file_contents},
            message=f"Successfully read {file_count} file(s) from {directory} (excluded {excluded_count} items)"
        )


class FileReaderPlugin(BasePlugin):
    """파일 경로 목록을 읽어 내용을 결합하는 플러그인"""
    
    name = "code_reader"
    description = "지정된 파일들을 읽어 내용을 결합합니다"
    
    file_paths: List[str]
    
    def run(self, state: CycleState, config: Dict[str, Any]) -> PluginResult:
        """설정된 파일 경로들을 읽어 내용을 결합합니다."""
        file_paths = config.get("file_paths", [])
        
        combined_content = []
        
        for file_path in file_paths:
            path = pathlib.Path(file_path)
            try:
                content = path.read_text(encoding='utf-8')
                combined_content.append(f"=== {file_path} ===\n{content}\n")
            except Exception as e:
                combined_content.append(f"=== {file_path} (ERROR) ===\nFailed to read: {str(e)}\n")
        
        file_contents = "\n".join(combined_content)
        
        return PluginResult(
            status="success",
            output={"file_contents": file_contents},
            state_updates={"file_contents": file_contents},
            message=f"Successfully read {len(file_paths)} file(s)"
        )

# 플러그인 등록
from plugins.registry import register_plugin

register_plugin(DirectoryReaderPlugin)

register_plugin(FileReaderPlugin)

