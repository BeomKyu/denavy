"""Core orchestration logic."""

from __future__ import annotations

import toml
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from denavy_common import (
    BasePlugin,
    CycleState,
    EventLogEntry,
    JudgeDecision,
    PluginConfig,
    PluginResult,
    Template,
)
from plugins.registry import get_plugin, list_plugins

from .llm import VetoEngine
from .log_writer import LogWriter
from .utils import create_cycle_id, render_event


class HybridOrchestrator:
    """Manages template loading, plugin execution, and state."""

    def __init__(
        self,
        templates_dir: Path,
        logs_dir: Path,
        console: Console,
    ) -> None:
        self.templates_dir = templates_dir
        self.logs_dir = logs_dir
        self.console = console

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
            raise FileNotFoundError(f"Template '{template_name}' not found at {template_file}")
        
        try:
            data = toml.load(template_file)
            return Template.model_validate(data["template"])
        except Exception as e:
            raise ValueError(f"Failed to load or parse template {template_file}: {e}")

    def _render_plan_prompt(self, steps: list[PluginConfig], state: CycleState) -> str:
        """Generate the prompt for the VetoEngine, now including user input."""
        
        plan_steps = "\n".join(f"- Step: {step.plugin}" for step in steps)
        
        discomfort = state.user_input
        
        prompt_parts = [
            "Review the user's discomfort (if any) and the proposed execution plan."
        ]
        
        if discomfort:
            prompt_parts.append(f"\nUser Discomfort:\n'''\n{discomfort}\n'''")
        
        prompt_parts.append(f"\nProposed Plan:\n{plan_steps}")
        
        return "\n".join(prompt_parts)

    def _evaluate_template(self, template: Template, state: CycleState) -> JudgeDecision:
        """Ask the VetoEngine (Judge) to approve or deny the template."""
        if template.judge is None:
            return JudgeDecision(approved=True, reason="No judge configured; auto-approving.")

        veto_engine = VetoEngine(
            model=template.judge.model,
            system_prompt=template.judge.system_prompt,
            **template.judge.model_dump(exclude={"model", "system_prompt"}),
        )
        
        plan_prompt = self._render_plan_prompt(template.steps, state)
        
        decision_dict = veto_engine.decide(plan_prompt)
        return JudgeDecision.model_validate(decision_dict)

    def run(self, template_name: str, cycle_id: Optional[str] = None) -> None:
        """Execute a full Denavy cycle."""
        
        start_time = datetime.utcnow()
        active_cycle_id = cycle_id or create_cycle_id(start_time)
        state = self._create_cycle_state(active_cycle_id)
        
        log_writer = LogWriter(self.logs_dir, active_cycle_id)
        
        try:
            template = self._load_template(template_name)
        except Exception as e:
            self.console.print(Panel(f"Fatal Error: {e}", title="Engine", style="bold red"))
            return

        decision = self._evaluate_template(template, state)
        self.console.print(Panel(
            decision.reason, 
            title="Veto Result", 
            style="green" if decision.approved else "red"
        ))

        if not decision.approved:
            next_plugin_name = self._handle_veto(state)
            if not next_plugin_name:
                self.console.print("[bold red]Cycle aborted by user.[/]")
                return
            
            steps_to_run = [PluginConfig(name=next_plugin_name, config={})]
        else:
            steps_to_run = template.steps

        events: List[EventLogEntry] = []
        for step in steps_to_run:
            plugin = get_plugin(step.plugin)
            if not plugin:
                self.console.print(f"[ERROR] Plugin '{step.plugin}' not found.", style="red")
                continue

            event, result = self._execute_step(state, plugin, step.config)
            events.append(event)
            log_writer.log_event(event)
            
            self._apply_plugin_result(state, result)
            
            if result.status == "error":
                self.console.print(f"[ERROR] Cycle halted due to error in {plugin.name}.", style="red")
                break
        
        if template.summary:
            summary_plugin = get_plugin(template.summary.plugin)
            if summary_plugin:
                summary_config = template.summary.config.copy()
                summary_config["events"] = events
                
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

    def _execute_step(
        self, 
        state: CycleState, 
        plugin: BasePlugin, 
        config: dict
    ) -> tuple[EventLogEntry, PluginResult]:
        """Execute a single plugin and generate its event log."""

        interpolated_config = config

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

    def _handle_veto(self, state: CycleState) -> Optional[str]:
        """(Temp) Fallback to manual plugin selection if Judge vetoes."""
        self.console.print("[yellow]Judge vetoed the plan. Available plugins:[/]")
        plugins = list(list_plugins())
        for i, name in enumerate(plugins):
            self.console.print(f"{i+1}. {name}")
        
        choice_str = Prompt.ask("Pick next plugin (number or name)", default="exit")
        
        if choice_str.lower() in ("exit", "quit"):
            return None
        
        try:
            idx = int(choice_str) - 1
            if 0 <= idx < len(plugins):
                return plugins[idx]
        except ValueError:
            pass
        
        if choice_str in plugins:
            return choice_str
            
        return None
