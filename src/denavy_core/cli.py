"""CLI entrypoint for Denavy."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

import plugins  # noqa: F401  # ensure built-in plugins register themselves

from .engine import HybridOrchestrator
from plugins.registry import list_plugins

app = typer.Typer(help="Denavy hybrid orchestrator")
console = Console()


@app.command()
def run(
    template: str = typer.Option("default_template", "--template", "-t", help="Template name without .toml"),
    cycle_id: Optional[str] = typer.Option(None, "--cycle-id", help="Override cycle identifier"),
    templates_dir: Path = typer.Option(Path("templates"), "--templates-dir", help="Directory containing templates"),
    logs_dir: Path = typer.Option(Path("logs"), "--logs-dir", help="Directory where logs are written"),
) -> None:
    """Execute a Denavy cycle."""

    orchestrator = HybridOrchestrator(templates_dir=templates_dir, logs_dir=logs_dir, console=console)
    orchestrator.run(template_name=template, cycle_id=cycle_id)


@app.command()
def plugins() -> None:
    """List registered plugins."""

    for plugin in list_plugins():
        console.print(f"- {plugin}")
