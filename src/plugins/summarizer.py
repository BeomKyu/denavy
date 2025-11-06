"""Naive summariser that creates Denavy's tiered logs."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, List

from denavy_common import (
    BasePlugin,
    CycleState,
    EventLogEntry,
    IndexRecord,
    PluginExecutionError,
    PluginResult,
    SummaryDocument,
)
from .registry import register_plugin


class SummarizerPlugin(BasePlugin):
    name = "summarizer"
    description = "Produces the L1 summary and L2 index artifacts for a cycle."

    def run(self, state: CycleState, config: dict) -> PluginResult:
        events = config.get("events") or []
        if not events:
            raise PluginExecutionError("Summarizer requires events in config")
        cast_events = list(self._as_event_iterable(events))
        highlights = self._build_highlights(cast_events)
        action_items = self._extract_action_items(cast_events)

        headline = state.get_value("user_input", "Denavy cycle summary")[:120]
        raw_lines = [
            f"{event.timestamp.isoformat()} | {event.plugin} | {event.status} | {event.message or ''}"
            for event in cast_events
        ]

        summary = SummaryDocument(
            cycle_id=state.cycle_id,
            generated_at=datetime.utcnow(),
            headline=headline,
            highlights=highlights,
            action_items=action_items,
            raw_text="\n".join(raw_lines),
        )

        index_record = IndexRecord(
            cycle_id=state.cycle_id,
            created_at=summary.generated_at,
            headline=headline,
            tags=list({*state.tags, "summary"}),
            summary_url=f"cycle_{state.cycle_id}/summary.json",
        )

        return PluginResult(
            status="success",
            output={"summary": summary, "index": index_record},
            message="Generated tiered logs",
        )

    def _as_event_iterable(self, events: Iterable[EventLogEntry]) -> Iterable[EventLogEntry]:
        for event in events:
            if isinstance(event, EventLogEntry):
                yield event

    def _build_highlights(self, events: List[EventLogEntry]) -> List[str]:
        highlights = []
        for event in events:
            if event.status == "success":
                highlights.append(f"{event.plugin} succeeded")
        return highlights[:5]

    def _extract_action_items(self, events: List[EventLogEntry]) -> List[str]:
        final_feedback = next((event.output_payload.get("feedback") for event in reversed(events) if event.plugin == "cli_feedback"), None)
        if final_feedback:
            return [f"Follow up on feedback: {final_feedback}"]
        return []


register_plugin(SummarizerPlugin)
