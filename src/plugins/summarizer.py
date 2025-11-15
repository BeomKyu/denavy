"""LLM-powered summariser that creates Denavy's tiered logs."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Iterable, List

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
from litellm import completion

DEFAULT_SUMMARY_PROMPT = """
You are a log summarizer for the Denavy system. You will receive a raw event log
from a completed cycle. Your task is to analyze the log and provide a concise
summary in JSON format.

The log format is: timestamp | plugin_name | status | message

Analyze the entire flow, from user_input to the final feedback.
Your *only* output must be a single, valid JSON object.
Do not add any text before or after the JSON.
Do not use markdown wrappers like ```json.

Respond with JSON containing:
- "headline": A short (max 120 chars) and descriptive title for the *entire cycle*,
              based on the user's initial discomfort or the final outcome.
- "highlights": A list of 3-5 strings. Each string should be a key event
                or outcome from the log (e.g., the plan proposed, the
                feedback given, or a critical error).
""".strip()


class SummarizerPlugin(BasePlugin):
    name = "summarizer"
    description = "Produces the L1 summary and L2 index artifacts for a cycle."

    def _generate_llm_summary(self, raw_log_text: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Call an LLM to generate headline and highlights."""
        model = config.get("model")
        if not model:
            return {}

        messages = [
            {"role": "system", "content": DEFAULT_SUMMARY_PROMPT},
            {"role": "user", "content": f"Here is the log:\n{raw_log_text}"},
        ]
        
        llm_kwargs = {
            "model": model,
            "messages": messages,
            "temperature": config.get("temperature", 0.1),
            "response_format": {"type": "json_object"},
        }

        try:
            response = completion(**llm_kwargs)
            message = response.choices[0].get("message", {}).get("content", "{}")
            return json.loads(message)
        except Exception as e:
            print(f"[WARN] Summarizer LLM failed: {e}")
            return {}

    def run(self, state: CycleState, config: dict) -> PluginResult:
        events = config.get("events") or []
        if not events:
            raise PluginExecutionError("Summarizer requires events in config")
        
        cast_events = list(self._as_event_iterable(events))
        
        raw_lines = [
            f"{event.timestamp.isoformat()} | {event.plugin} | {event.status} | {event.message or ''}"
            for event in cast_events
        ]
        raw_text = "\n".join(raw_lines)

        llm_summary = self._generate_llm_summary(raw_text, config)

        action_items = self._extract_action_items(cast_events)
        
        fallback_headline = (state.user_input or "Denavy cycle summary")[:120]
        
        fallback_highlights = self._build_highlights(
            cast_events, 
            config.get("max_highlight_len", 100)
        )

        headline = llm_summary.get("headline", fallback_headline)
        highlights = llm_summary.get("highlights", fallback_highlights)

        summary = SummaryDocument(
            cycle_id=state.cycle_id,
            generated_at=datetime.utcnow(),
            headline=headline,
            highlights=highlights,
            action_items=action_items,
            raw_text=raw_text,
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
            message="Generated tiered logs (LLM-assisted)",
        )

    def _as_event_iterable(self, events: Iterable[EventLogEntry]) -> Iterable[EventLogEntry]:
        for event in events:
            if isinstance(event, EventLogEntry):
                yield event

    def _build_highlights(self, events: List[EventLogEntry], max_len: int) -> List[str]:
        highlights = []
        for event in events:
            if event.status == "success":
                highlight_text = f"{event.plugin} succeeded"
                if event.plugin == "simple_llm_resolver" and "resolution" in event.output_payload:
                    resolution = event.output_payload["resolution"]
                    highlight_text = f"{event.plugin}: {resolution[:max_len]}{'...' if len(resolution) > max_len else ''}"
                elif event.plugin == "cli_feedback" and "user_feedback" in event.output_payload:
                    feedback = event.output_payload["user_feedback"]
                    highlight_text = f"{event.plugin}: {feedback[:max_len]}{'...' if len(feedback) > max_len else ''}"

                if len(highlights) < 5:
                    highlights.append(highlight_text)
        return highlights

    def _extract_action_items(self, events: List[EventLogEntry]) -> List[str]:
        action_items = []

        resolution = next((
            event.output_payload.get("resolution") 
            for event in reversed(events) 
            if event.plugin == "simple_llm_resolver" and event.output_payload.get("resolution")
        ), None)
        
        if resolution:
            summary_resolution = f"Review proposed plan: {resolution[:150]}{'...' if len(resolution) > 150 else ''}"
            action_items.append(summary_resolution)

        final_feedback = next((
            event.output_payload.get("user_feedback") 
            for event in reversed(events) 
            if event.plugin == "cli_feedback" and event.output_payload.get("user_feedback")
        ), None)
        
        if final_feedback:
            action_items.append(f"Follow up on feedback: {final_feedback}")

        return action_items


register_plugin(SummarizerPlugin)
