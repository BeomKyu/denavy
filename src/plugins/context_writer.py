# src/plugins/context_writer.py ('진화'된 코드)

from __future__ import annotations
import pathlib
from typing import Any, Dict

from denavy_common import BasePlugin, CycleState, PluginResult, PluginExecutionError
from .registry import register_plugin


class ContextWriterPlugin(BasePlugin):
    name = "context_writer"
    description = "Writes state.file_contents to a specified output file."

    def run(self, state: CycleState, config: Dict[str, Any]) -> PluginResult:
        file_contents = state.file_contents
        if not file_contents:
            raise PluginExecutionError("No file_contents found in state to write.")
        
        # '진화': 기본 경로를 'outputs/' 폴더 하위로 변경
        output_dir = pathlib.Path(config.get("output_dir", "outputs"))
        output_filename = config.get("output_file", "notebooklm_context.txt")
        
        # '진화': 폴더가 없으면 생성 (logs/ 폴더 로직과 유사)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / output_filename
        
        try:
            output_path.write_text(file_contents, encoding="utf-8")
            message = f"Successfully wrote context to {output_path.resolve()}"
            return PluginResult(status="success", message=message, output={"output_path": str(output_path)})
        except Exception as e:
            raise PluginExecutionError(f"Failed to write to {output_path}: {e}")

register_plugin(ContextWriterPlugin)
