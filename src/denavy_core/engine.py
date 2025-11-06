"""Hybrid orchestrator implementing the Denavy v6 hypothesis."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel

from denavy_common import (
    BasePlugin,
    CycleState,
    EventLogEntry,
    IndexRecord,
    JudgeDecision,
    PluginExecutionError,
    PluginResult,
    SummaryDocument,
)

from .llm import VetoEngine
from .log_writer import CycleLogWriter
from .template_loader import TemplateLoader
from plugins.registry import get_plugin


class HybridOrchestrator:
    """Coordinates template execution, veto checks, and logging."""

    def __init__(
        self,
        templates_dir: Path | str = Path("templates"),
        logs_dir: Path | str = Path("logs"),
        console: Optional[Console] = None,
    ) -> None:
        self.templates_dir = Path(templates_dir)
        self.logs_dir = Path(logs_dir)
        self.console = console or Console()
        self.template_loader = TemplateLoader(self.templates_dir)
        self.log_writer = CycleLogWriter(self.logs_dir)

    def run(self, template_name: str = "default_template", cycle_id: Optional[str] = None) -> None:
        template_doc = self.template_loader.load(template_name)
        cycle_identifier = cycle_id or datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        state = CycleState(cycle_id=cycle_identifier, created_at=datetime.utcnow())
        events: List[EventLogEntry] = []

        decision = self._evaluate_template(template_doc, state)
        if decision.approved:
            self.console.print(Panel.fit(f"Template approved: {decision.reason}", title="Veto Result"))
            self._run_sequenced_steps(template_doc, state, events)
        else:
            self.console.print(Panel.fit(f"Template vetoed: {decision.reason}", title="Veto Result", style="yellow"))
            self._run_dynamic_mode(state, events)

        summary, index_record = self._generate_logs(template_doc, state, events)
        self.log_writer.write(events, summary, index_record)
        self.console.print(Panel.fit(f"Cycle {state.cycle_id} completed", title="denavy"))

    def _evaluate_template(self, template_doc: Dict[str, Any], state: CycleState) -> JudgeDecision:
        judge_config = template_doc["template"].get("judge")
        if not judge_config:
            return JudgeDecision(approved=True, reason="No judge configured; default approve")

        prompt = self._render_plan_prompt(template_doc, state)
        try:
            veto = VetoEngine(
                model=judge_config.get("model", "gpt-4o-mini"),
                system_prompt=judge_config.get("system_prompt"),
                temperature=judge_config.get("temperature", 0),
            )
            response = veto.decide(prompt)
            approved = bool(response.get("approved", True))
            reason = str(response.get("reason", "Judge did not provide a reason"))
            return JudgeDecision(approved=approved, reason=reason, raw_response=response)
        except Exception as exc:  # noqa: BLE001
            self.console.print(Panel.fit(f"Judge invocation failed: {exc}", title="Veto", style="red"))
            return JudgeDecision(approved=True, reason="Judge unavailable; fallback to approve")

    def _render_plan_prompt(self, template_doc: Dict[str, Any], state: CycleState) -> str:
        steps = template_doc["template"].get("steps", [])
        step_lines = [f"- {idx + 1}. {step.get('plugin')}" for idx, step in enumerate(steps)]
        tags = ", ".join(state.tags) or "[no tags yet]"
        return "\n".join(
            [
                f"Cycle: {state.cycle_id}",
                f"Existing tags: {tags}",
                "Proposed pipeline:",
                *step_lines,
            ]
        )

    def _run_sequenced_steps(self, template_doc: Dict[str, Any], state: CycleState, events: List[EventLogEntry]) -> None:
        for raw_step in template_doc["template"].get("steps", []):
            plugin_name = raw_step.get("plugin")
            config = raw_step.get("config", {})
            self._invoke_plugin(plugin_name, config, state, events)

    def _run_dynamic_mode(self, state: CycleState, events: List[EventLogEntry]) -> None:
        self.console.print(Panel.fit("Entering dynamic mode. Type 'done' to finish.", title="Dynamic Mode", style="cyan"))
        while True:
            choice = self.console.input("Pick next plugin (or 'done'): ").strip()
            if not choice:
                continue
            if choice.lower() == "done":
                break
            config: Dict[str, Any] = {}
            self._invoke_plugin(choice, config, state, events)

    def _invoke_plugin(self, plugin_name: str, config: Dict[str, Any], state: CycleState, events: List[EventLogEntry]) -> None:
        plugin = self._resolve_plugin(plugin_name)
        started = datetime.utcnow()
        input_payload = {"config": config, "state_snapshot": state.context.copy()}
        try:
            result = plugin.run(state, config)
            self._apply_plugin_result(result, state)
            status = result.status
            message = result.message
            output_payload = result.output
        except PluginExecutionError as exc:
            status = "error"
            message = str(exc)
            output_payload = {}
        except Exception as exc:  # noqa: BLE001
            status = "error"
            message = f"Unexpected failure: {exc}"
            output_payload = {}
        event = EventLogEntry(
            timestamp=started,
            cycle_id=state.cycle_id,
            plugin=plugin.name,
            status=status,
            input_payload=input_payload,
            output_payload=output_payload,
            message=message,
        )
        events.append(event)
        self.console.print(f"[{status}] {plugin.name}: {message or 'ok'}")

    def _apply_plugin_result(self, result: PluginResult, state: CycleState) -> None:
        for key, value in result.state_updates.items():
            state.set_value(key, value)
        if result.tags:
            state.add_tags(result.tags)
        if "note" in result.output:
            note = result.output["note"]
            if isinstance(note, str):
                state.add_note(note)

    def _resolve_plugin(self, plugin_name: str) -> BasePlugin:
        plugin = get_plugin(plugin_name)
        if not plugin:
            raise PluginExecutionError(f"Unknown plugin '{plugin_name}'")
        return plugin

    def _generate_logs(
        self,
        template_doc: Dict[str, Any],
        state: CycleState,
        events: List[EventLogEntry],
    ) -> tuple[SummaryDocument, IndexRecord]:
        summary_config = template_doc["template"].get("summary", {"plugin": "summarizer", "config": {}})
        plugin_name = summary_config.get("plugin", "summarizer")
        config = summary_config.get("config", {})
        plugin = self._resolve_plugin(plugin_name)
        result = plugin.run(state, {**config, "events": events})
        summary_payload = result.output.get("summary")
        index_payload = result.output.get("index")
        if not isinstance(summary_payload, SummaryDocument) or not isinstance(index_payload, IndexRecord):
            raise PluginExecutionError("Summarizer plugin must return SummaryDocument and IndexRecord")

        events.append(
            EventLogEntry(
                timestamp=datetime.utcnow(),
                cycle_id=state.cycle_id,
                plugin=plugin.name,
                status=result.status,
                input_payload={"config": config},
                output_payload={"summary_headline": summary_payload.headline},
                message=result.message,
            )
        )

        return summary_payload, index_payload
