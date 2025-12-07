"""Plugin to execute code or commands and capture output."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

from denavy_common import BasePlugin, CycleState, PluginResult


class ExecutorPlugin(BasePlugin):
    name = "executor"
    description = "Executes shell commands or Python code files and captures output."

    def run(self, state: CycleState, config: Dict[str, Any]) -> PluginResult:
        command = config.get("command")
        code = config.get("code")
        filename = config.get("filename")

        # '진화': Context Awareness - Try to parse code from previous steps (proposed_resolution)
        # if explicit config is missing.
        if not code and not filename and not command:
            resolution = state.proposed_resolution
            if resolution:
                # Try to extract FILENAME: ... CODE: ... format (simple parsing)
                import re

                # Check for FILENAME pattern
                fn_match = re.search(r"FILENAME:\s*(\S+)", resolution)
                if fn_match:
                    filename = fn_match.group(1).strip()

                # Check for Code block
                code_match = re.search(r"```(?:python)?\n(.*?)```", resolution, re.DOTALL)
                if code_match:
                    code = code_match.group(1)

        # 1. Write code to file if provided
        if code and filename:
            try:
                filepath = Path(filename)
                filepath.parent.mkdir(parents=True, exist_ok=True)
                filepath.write_text(code, encoding="utf-8")
                state.add_note(f"Wrote code to {filename}")
            except Exception as e:
                return PluginResult(
                    status="error",
                    message=f"Failed to write file {filename}: {e}",
                    output={"error": str(e)}
                )

        # 2. Determine command to run
        if not command:
            if filename and filename.endswith(".py"):
                command = f"{sys.executable} {filename}"
            elif filename:
                # Try to run as executable or cat it? Default to assuming it's a script.
                command = f"./{filename}"
            else:
                 return PluginResult(
                    status="error",
                    message="No command or executable filename provided.",
                    output={}
                )

        # 3. Execute
        try:
            state.add_note(f"Executing: {command}")
            # Run with timeout to prevent hanging
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=config.get("timeout", 60)
            )

            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            return_code = result.returncode

            output_payload = {
                "stdout": stdout,
                "stderr": stderr,
                "return_code": return_code,
                "command": command
            }

            status = "success" if return_code == 0 else "error"
            message = f"Command finished with code {return_code}"

            if return_code != 0:
                message += f". Stderr: {stderr[:200]}..." # Truncate for summary

            return PluginResult(
                status=status,
                message=message,
                output=output_payload,
                scratchpad_updates={"last_execution": output_payload}
            )

        except subprocess.TimeoutExpired:
            return PluginResult(
                status="error",
                message="Execution timed out.",
                output={"timeout": True}
            )
        except Exception as e:
            return PluginResult(
                status="error",
                message=f"Execution failed: {e}",
                output={"error": str(e)}
            )
