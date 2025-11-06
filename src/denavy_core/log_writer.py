"""Helpers for persisting Denavy's three-tier log artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from denavy_common import EventLogEntry, IndexRecord, SummaryDocument


class CycleLogWriter:
    """Writes cycle events, summaries, and index records to disk."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def write(self, events: Iterable[EventLogEntry], summary: SummaryDocument, index_record: IndexRecord) -> None:
        cycle_dir = self.base_dir / f"cycle_{summary.cycle_id}"
        cycle_dir.mkdir(parents=True, exist_ok=True)

        events_path = cycle_dir / "events.jsonl"
        with events_path.open("w", encoding="utf-8") as events_file:
            for event in events:
                events_file.write(json.dumps(event.model_dump(mode="json"), ensure_ascii=True) + "\n")

        summary_path = cycle_dir / "summary.json"
        with summary_path.open("w", encoding="utf-8") as summary_file:
            json.dump(summary.model_dump(mode="json"), summary_file, ensure_ascii=True, indent=2)

        index_path = self.base_dir / "index.jsonl"
        with index_path.open("a", encoding="utf-8") as index_file:
            index_file.write(json.dumps(index_record.model_dump(mode="json"), ensure_ascii=True) + "\n")
