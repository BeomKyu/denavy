"""Helpers for persisting Denavy's three-tier log artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from denavy_common import EventLogEntry, IndexRecord, SummaryDocument


class LogWriter:
    """Writes cycle events, summaries, and index records to disk."""

    def __init__(self, base_dir: Path, cycle_id: str) -> None:
        self.base_dir = base_dir
        self.cycle_id = cycle_id
        self.cycle_dir = self.base_dir / f"cycle_{cycle_id}"
        self.cycle_dir.mkdir(parents=True, exist_ok=True)

    def log_event(self, event: EventLogEntry) -> None:
        """Append a single event to the events.jsonl file."""
        events_path = self.cycle_dir / "events.jsonl"
        with events_path.open("a", encoding="utf-8") as events_file:
            events_file.write(json.dumps(event.model_dump(mode="json"), ensure_ascii=True) + "\n")

    def write_summary_artifacts(
        self, 
        summary: Optional[SummaryDocument], 
        index_record: Optional[IndexRecord]
    ) -> None:
        """Write the final summary.json and append to the global index.jsonl."""
        
        if summary:
            summary_path = self.cycle_dir / "summary.json"
            with summary_path.open("w", encoding="utf-8") as summary_file:
                json.dump(summary.model_dump(mode="json"), summary_file, ensure_ascii=True, indent=2)

        if index_record:
            index_path = self.base_dir / "index.jsonl"
            with index_path.open("a", encoding="utf-8") as index_file:
                index_file.write(json.dumps(index_record.model_dump(mode="json"), ensure_ascii=True) + "\n")
