"""General utilities for the Denavy core engine."""

from __future__ import annotations

from datetime import datetime

from denavy_common import EventLogEntry


def create_cycle_id(timestamp: datetime) -> str:
    """Generate a human-readable, sortable cycle ID."""
    return timestamp.strftime("%Y%m%d-%H%M%S")


def render_event(event: EventLogEntry) -> str:
    """Render a single log event for the console."""
    style = "green" if event.status == "success" else "red"
    
    message = event.message or ""
    
    if len(message) > 70:
        message = message[:67] + "..."
        
    return f" [dim]{event.plugin}:[/] [{style}]{event.status}[/] [dim]{message}[/]"