"""Core Execution Engine logic."""

from __future__ import annotations

import toml
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Deque

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from denavy_common import (
    BasePlugin,
    CycleState,
    EventLogEntry,
    PluginConfig,
    PluginResult,
    Template,
)
from plugins.registry import get_plugin

from .judge import Judge
from .planner import Planner
from .log_writer import LogWriter
from .utils import create_cycle_id, render_event


class ExecutionEngine:
    """Orchestrates plugin execution with a dynamic task queue and self-repair capabilities."""

    def __init__(
        self,
        templates_dir: Path,
        logs_dir: Path,
        console: Console,
        planner_model: str = "gpt-4-turbo", # Default planner model
    ) -> None:
        self.templates_dir = templates_dir
        self.logs_dir = logs_dir
        self.console = console

        self.judge = Judge(templates_dir)
        self.planner = Planner(model=planner_model)

        self._recursion_depth = 0
        self._max_repair_attempts = 3

    def _create_cycle_state(self, cycle_id: str) -> CycleState:
        """Initialize a new, empty state for a cycle."""
        return CycleState(
            cycle_id=cycle_id,
            created_at=datetime.utcnow(),
        )

    def _load_template(self, template_name: str) -> Template:
        """Load and parse a TOML template file."""
        template_file = (self.templates_dir / f"{template_name}.toml").resolve()
        if not template_file.is_file():
            # If not found, try adding .toml extension if missing
            if not template_name.endswith(".toml"):
                 template_file = (self.templates_dir / f"{template_name}.toml").resolve()

            if not template_file.is_file():
                raise FileNotFoundError(f"Template '{template_name}' not found at {template_file}")
        
        try:
            data = toml.load(template_file)
            return Template.model_validate(data["template"])
        except Exception as e:
            raise ValueError(f"Failed to load or parse template {template_file}: {e}")

    def run(self, template_name: str, cycle_id: Optional[str] = None) -> None:
        """Execute a full Denavy cycle."""
        
        # Prevent infinite loops in evolution/repair
        if self._recursion_depth > 5:
             self.console.print("[bold red]Max recursion depth reached. Stopping.[/]")
             return

        start_time = datetime.utcnow()
        active_cycle_id = cycle_id or create_cycle_id(start_time)
        state = self._create_cycle_state(active_cycle_id)
        
        log_writer = LogWriter(self.logs_dir, active_cycle_id)
        
        try:
            template = self._load_template(template_name)
        except Exception as e:
            self.console.print(Panel(f"Fatal Error: {e}", title="Engine", style="bold red"))
            return

        # --- Phase 1: Pre-Execution & Context Gathering ---
        # The first step of a template usually gathers input. Run it immediately.
        # This logic is kept from the original to ensure `state.user_input` is populated for the Judge.
        initial_steps = list(template.steps) # Copy
        events: List[EventLogEntry] = []

        if initial_steps and "input" in initial_steps[0].plugin:
            first_step = initial_steps.pop(0)
            plugin = get_plugin(first_step.plugin)
            if plugin:
                self.console.print(f"[dim]Pre-executing {first_step.plugin} to capture context...[/]")
                event, result = self._execute_step(state, plugin, first_step.config)
                events.append(event)
                log_writer.log_event(event)
                self._apply_plugin_result(state, result)
                if result.status == "error":
                    self.console.print(f"[ERROR] Cycle halted during pre-execution.", style="red")
                    return

        # --- Phase 2: Judgment (Veto) ---
        decision = self.judge.evaluate_template(template, state)
        self.console.print(Panel(
            decision.reason, 
            title="Veto Result", 
            style="green" if decision.approved else "red"
        ))

        queue: Deque[PluginConfig] = deque()

        if decision.approved:
            queue.extend(initial_steps)
        else:
            if decision.recommended_template:
                self.console.print(f"[bold yellow]Judge suggests switching to: {decision.recommended_template}[/]")
                # In a CLI tool, asking is fine. For fully autonomous, we might auto-accept based on config.
                confirm = Prompt.ask("Switch to this template?", choices=["y", "n"], default="y")
                if confirm == "y":
                    self._recursion_depth += 1
                    try:
                        self.run(decision.recommended_template, cycle_id=active_cycle_id)
                    finally:
                        self._recursion_depth -= 1
                    return

            # If rejected and no template switch, ask Planner for a dynamic plan
            self.console.print("[yellow]Plan rejected. Asking Planner for a dynamic plan...[/]")
            dynamic_plan = self.planner.generate_plan(state, context_msg=f"Original plan rejected. Judge reason: {decision.reason}")
            queue.extend(dynamic_plan)
            if not queue:
                 self.console.print("[red]Planner could not generate a plan. Aborting.[/]")
                 return

        # --- Phase 3: Dynamic Execution Loop ---
        execution_trace: List[EventLogEntry] = list(events) # Keep tracking events
        
        current_repair_attempts = 0 # Track repair attempts for the current cycle

        while queue:
            step = queue.popleft()
            plugin = get_plugin(step.plugin)

            if not plugin:
                self.console.print(f"[ERROR] Plugin '{step.plugin}' not found. Asking Planner to fix...", style="red")

                if current_repair_attempts >= self._max_repair_attempts:
                     self.console.print(f"[bold red]Max repair attempts ({self._max_repair_attempts}) reached. Aborting.[/]")
                     break

                current_repair_attempts += 1

                # Dynamic Repair: Ask planner to provide an alternative for this missing plugin
                repair_steps = self._trigger_repair(state, f"Plugin '{step.plugin}' not found.")
                # Prepend repair steps
                for s in reversed(repair_steps):
                    queue.appendleft(s)
                continue

            event, result = self._execute_step(state, plugin, step.config)
            execution_trace.append(event)
            log_writer.log_event(event)
            self._apply_plugin_result(state, result)
            
            if result.status == "error":
                self.console.print(f"[bold red]Step '{step.plugin}' Failed: {result.message}[/]")

                if current_repair_attempts >= self._max_repair_attempts:
                     self.console.print(f"[bold red]Max repair attempts ({self._max_repair_attempts}) reached. Aborting.[/]")
                     break

                current_repair_attempts += 1

                repair_steps = self._trigger_repair(state, f"Step '{step.plugin}' failed: {result.message}")
                if repair_steps:
                    self.console.print(f"[green]Planner provided {len(repair_steps)} repair steps. Injecting...[/]")
                    for s in reversed(repair_steps):
                        queue.appendleft(s)
                else:
                    self.console.print("[red]Planner could not provide a fix. Halting cycle.[/]")
                    break
            else:
                 # Reset repair attempts on success, assuming we are making progress
                 # NOTE: This simple reset might lead to loops if we fix A then fail B then fix A...
                 # For now, it's acceptable for a basic self-repair loop.
                 current_repair_attempts = 0

        # --- Phase 4: Summarization & Finalization ---
        if template.summary:
            summary_plugin = get_plugin(template.summary.plugin)
            if summary_plugin:
                summary_config = template.summary.config.copy()
                summary_config["events"] = execution_trace
                event, result = self._execute_step(state, summary_plugin, summary_config)
                log_writer.log_event(event)
                self._apply_plugin_result(state, result)
                if result.status == "success":
                     log_writer.write_summary_artifacts(
                        result.output.get("summary"),
                        result.output.get("index")
                    )

        self.console.print(Panel(
            f"Cycle {active_cycle_id} completed", 
            title="denavy", 
            style="cyan"
        ))
        
        # TODO: Phase 5 (Evolution) logic can be reintegrated here similar to the old engine
        # self._check_and_trigger_evolution(state, active_cycle_id)

    def _trigger_repair(self, state: CycleState, error_msg: str) -> List[PluginConfig]:
        """Ask the Planner for remedial steps."""
        self.console.print(f"[dim]Triggering Self-Repair for: {error_msg}[/]")
        try:
             return self.planner.generate_plan(state, context_msg=f"Repair needed. Error: {error_msg}")
        except Exception as e:
            self.console.print(f"[bold red]Planner failed during repair generation: {e}[/]")
            return []

    def _execute_step(
        self, 
        state: CycleState, 
        plugin: BasePlugin, 
        config: dict
    ) -> tuple[EventLogEntry, PluginResult]:
        """Execute a single plugin and generate its event log."""
        interpolated_config = config # TODO: Add variable interpolation support if needed
        event = EventLogEntry(
            timestamp=datetime.utcnow(),
            cycle_id=state.cycle_id,
            plugin=plugin.name,
            status="success",
            input_payload=interpolated_config,
        )
        try:
            result = plugin.run(state, interpolated_config)
            event.status = result.status
            event.output_payload = result.output
            event.message = result.message
            event.tags = result.tags
            self.console.print(render_event(event))
            return event, result
        except Exception as e:
            event.status = "error"
            event.message = str(e)
            self.console.print(render_event(event))
            return event, PluginResult(status="error", message=str(e))

    def _apply_plugin_result(self, state: CycleState, result: PluginResult) -> None:
        """Apply updates from a plugin's result to the main cycle state."""
        if result.user_input is not None:
            state.user_input = result.user_input
        if result.file_contents is not None:
            state.file_contents = result.file_contents
        if result.proposed_resolution is not None:
            state.proposed_resolution = result.proposed_resolution
        if result.user_feedback is not None:
            state.user_feedback = result.user_feedback
        state.scratchpad.update(result.scratchpad_updates)
        state.add_tags(result.tags)
