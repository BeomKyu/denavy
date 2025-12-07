"""The Execution Engine."""

from __future__ import annotations

import toml
from collections import deque
from pathlib import Path
from typing import Deque, Optional, Any

from rich.console import Console
from rich.panel import Panel

from denavy.domain import CycleState, PluginConfig, Template, EventLog, PluginResult
from denavy.core.judge import Judge
from denavy.core.planner import Planner
from denavy.plugins.registry import get_plugin

class ExecutionEngine:
    def __init__(self, templates_dir: Path, logs_dir: Path, console: Console = None):
        self.templates_dir = templates_dir
        self.logs_dir = logs_dir
        self.console = console or Console()
        self.judge = Judge()
        self.planner = Planner()

        self._recursion_depth = 0
        self._max_repairs = 3

    def run(self, template_name: str, cycle_id: str = "default") -> None:
        if self._recursion_depth > 5:
            self.console.print("[red]Max recursion depth.[/]")
            return

        state = CycleState(cycle_id=cycle_id)

        # Load Template
        try:
            template = self._load_template(template_name)
        except Exception as e:
            self.console.print(f"[red]Failed to load template: {e}[/]")
            return

        # Judge
        decision = self.judge.evaluate(template, state)
        if not decision.approved:
            self.console.print(f"[red]Judge Vetoed: {decision.reason}[/]")
            if decision.recommended_template:
                self.console.print(f"[yellow]Switching to {decision.recommended_template}[/]")
                self._recursion_depth += 1
                try:
                    self.run(decision.recommended_template, cycle_id)
                finally:
                    self._recursion_depth -= 1
            return

        self.console.print(f"[green]Plan Approved: {template.name}[/]")

        # Execution Queue
        queue: Deque[PluginConfig] = deque(template.steps)
        current_repairs = 0

        while queue:
            step = queue.popleft()

            # Find Plugin
            plugin_cls = get_plugin(step.plugin)
            if not plugin_cls:
                self.console.print(f"[red]Plugin '{step.plugin}' not found.[/]")
                # Self-repair logic for missing plugin could go here
                continue

            plugin = plugin_cls()
            self.console.print(f"[bold cyan]Running {plugin.name}...[/]")

            try:
                # Dynamic Context Interpolation (Simple)
                # If code/filename missing in config, check state
                config = step.config.copy()
                if plugin.name == "executor" and not config.get("code"):
                     if state.proposed_resolution and "```" in state.proposed_resolution:
                         # Extract code from proposed_resolution
                         import re
                         match = re.search(r"```(?:python)?\n(.*?)```", state.proposed_resolution, re.DOTALL)
                         if match:
                             config["code"] = match.group(1)
                             # Extract filename
                             fn_match = re.search(r"FILENAME:\s*(\S+)", state.proposed_resolution)
                             if fn_match:
                                 config["filename"] = fn_match.group(1).strip()
                             else:
                                 config["filename"] = "generated_script.py"

                result = plugin.run(state, config)
                state.update(result)

                # Log Event (Simplified)
                # self.log_event(...)

                if result.status == "error":
                    self.console.print(f"[red]Error in {step.plugin}: {result.message}[/]")
                    if current_repairs < self._max_repairs:
                        self.console.print("[yellow]Triggering Self-Repair...[/]")
                        repairs = self.planner.generate_plan(state, f"Step {step.plugin} failed: {result.message}")
                        for r in reversed(repairs):
                            queue.appendleft(r)
                        current_repairs += 1
                    else:
                        self.console.print("[bold red]Max repairs reached. Aborting.[/]")
                        break
                else:
                    self.console.print(f"[dim]Output: {result.message}[/]")
                    current_repairs = 0 # Reset repairs on success

            except Exception as e:
                self.console.print(f"[red]System Error executing {step.plugin}: {e}[/]")
                break

        self.console.print(f"[bold green]Cycle {cycle_id} Completed.[/]")

    def _load_template(self, name: str) -> Template:
        path = self.templates_dir / f"{name}.toml"
        if not path.exists():
            raise FileNotFoundError(f"{path} not found")
        data = toml.load(path)
        return Template(**data["template"])
