"""Plugin to commit and push changes to git."""

from __future__ import annotations

import subprocess
from typing import Any, Dict

from denavy_common import BasePlugin, CycleState, PluginResult


class GitCommitterPlugin(BasePlugin):
    name = "git_committer"
    description = "Commits and pushes changes to the git repository."

    def run(self, state: CycleState, config: Dict[str, Any]) -> PluginResult:
        message = config.get("message", f"Auto-commit from cycle {state.cycle_id}")
        branch = config.get("branch", "main")
        push = config.get("push", True)
        files = config.get("files", ".") # Default to all files

        output_log = []

        def run_git(args: list[str]) -> bool:
            cmd = ["git"] + args
            result = subprocess.run(cmd, capture_output=True, text=True)
            output_log.append(f"$ {' '.join(cmd)}\n{result.stdout}\n{result.stderr}")
            return result.returncode == 0

        # 1. Add
        if not run_git(["add", files]):
             return PluginResult(status="error", message="git add failed", output={"log": output_log})

        # 2. Commit
        # Check if there are changes first? git commit will fail if empty, which is fine to catch.
        if not run_git(["commit", "-m", message]):
             # If commit fails, it might be because nothing to commit.
             return PluginResult(
                 status="success", # Treat no-changes as success-ish or warning?
                 message="git commit failed (possibly nothing to commit)",
                 output={"log": output_log}
            )

        # 3. Push
        if push:
            # We assume remote 'origin' exists.
            # In some CI/Agent envs, we might not have permissions or upstream set.
            # We'll try, but return error if fails.
            if not run_git(["push", "origin", branch]):
                 return PluginResult(status="error", message="git push failed", output={"log": output_log})

        return PluginResult(
            status="success",
            message="Git operations completed successfully.",
            output={"log": output_log}
        )
