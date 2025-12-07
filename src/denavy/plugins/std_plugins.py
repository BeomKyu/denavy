"""Standard Plugins."""

import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

from denavy.domain import BasePlugin, CycleState, PluginResult
from denavy.plugins.registry import register_plugin
from denavy.llm import LLMService

@register_plugin
class ExecutorPlugin(BasePlugin):
    name = "executor"

    def run(self, state: CycleState, config: Dict[str, Any]) -> PluginResult:
        command = config.get("command")
        code = config.get("code")
        filename = config.get("filename")

        if code and filename:
            try:
                Path(filename).write_text(code, encoding="utf-8")
            except Exception as e:
                return PluginResult(status="error", message=f"Write failed: {e}")

        if not command:
            if filename:
                command = f"{sys.executable} {filename}" if filename.endswith(".py") else f"./{filename}"
            else:
                return PluginResult(status="error", message="No command or filename.")

        try:
            # Run
            res = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60)
            status = "success" if res.returncode == 0 else "error"
            output = {"stdout": res.stdout, "stderr": res.stderr, "rc": res.returncode}
            return PluginResult(
                status=status,
                message=f"RC: {res.returncode}. {res.stderr[:100]}",
                output=output,
                scratchpad_updates={"last_run": output}
            )
        except Exception as e:
            return PluginResult(status="error", message=str(e))


@register_plugin
class GitCommitterPlugin(BasePlugin):
    name = "git_committer"

    def run(self, state: CycleState, config: Dict[str, Any]) -> PluginResult:
        msg = config.get("message", "Auto-commit")

        def git(args):
            return subprocess.run(["git"] + args, capture_output=True, text=True)

        git(["add", "."])
        res = git(["commit", "-m", msg])

        # Push is optional/dangerous in auto-mode, verify config
        if config.get("push", False):
            git(["push"])

        return PluginResult(status="success", message="Git ops finished", output={"log": res.stdout})


@register_plugin
class CLIInputPlugin(BasePlugin):
    name = "cli_input"

    def run(self, state: CycleState, config: Dict[str, Any]) -> PluginResult:
        from rich.prompt import Prompt
        prompt = config.get("prompt", "Input:")
        user_input = Prompt.ask(prompt)
        return PluginResult(user_input=user_input)


@register_plugin
class SimpleLLMPlugin(BasePlugin):
    name = "simple_llm"

    def run(self, state: CycleState, config: Dict[str, Any]) -> PluginResult:
        llm = LLMService()
        sys_prompt = config.get("system_prompt", "You are a helpful assistant.")
        user_prompt = config.get("user_prompt", state.user_input or "")

        # Append previous error context if available
        last_run = state.scratchpad.get("last_run")
        if last_run and last_run.get("rc") != 0:
            user_prompt += f"\n\nPrevious Error:\n{last_run['stderr']}\nFix the code."

        result = llm.call(sys_prompt, user_prompt)
        return PluginResult(proposed_resolution=str(result))
