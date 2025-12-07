"""Denavy CLI."""

import typer
from pathlib import Path
from rich.console import Console

# Register plugins
import denavy.plugins.std_plugins
from denavy.core.engine import ExecutionEngine

app = typer.Typer()
console = Console()

@app.command()
def run(
    template: str = typer.Argument("self_repair"),
    templates_dir: Path = typer.Option(Path("templates")),
    logs_dir: Path = typer.Option(Path("logs"))
):
    """Run a Denavy cycle."""
    engine = ExecutionEngine(templates_dir, logs_dir, console)
    engine.run(template)

if __name__ == "__main__":
    app()
