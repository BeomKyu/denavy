from denavy_common import BasePlugin, CycleState, PluginResult
import pathlib
from typing import Dict, Any, List


class CodeReaderPlugin(BasePlugin):
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

register_plugin(CodeReaderPlugin)

