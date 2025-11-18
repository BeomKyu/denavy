"""CLI entrypoint for Denavy."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

# '진화': .env 파일 자동 로드 (설치된 경우)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass # denavy init 실행 전일 수 있음

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
    # (기존 코드 유지)
    orchestrator = HybridOrchestrator(templates_dir=templates_dir, logs_dir=logs_dir, console=console)
    orchestrator.run(template_name=template, cycle_id=cycle_id)


@app.command()
def plugins() -> None:
    """List registered plugins."""
    # (기존 코드 유지)
    for plugin in list_plugins():
        console.print(f"- {plugin}")


# '진화': 초기 설정 마법사 추가
@app.command()
def init(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing config without asking")
) -> None:
    """Initialize Denavy configuration and API keys."""
    console.print(Panel("🧙‍♂️ Denavy Setup Wizard", style="bold blue"))

    # 1. 기본 디렉터리 생성
    _create_directories(["templates", "logs", "outputs", "src/plugins"])

    # 2. .env 파일 생성 (API 키 설정)
    env_path = Path(".env")
    if env_path.exists() and not force:
        if not Confirm.ask(f"Found existing '{env_path}'. Overwrite?"):
            console.print("[yellow]Skipping .env setup.[/]")
            return

    console.print("\n[bold]🔑 API Key Setup[/]")
    console.print("Denavy uses [bold]LiteLLM[/], so we need to set up your provider's API Key.")
    
    provider = Prompt.ask(
        "Select your primary LLM Provider", 
        choices=["OpenAI", "Gemini", "Anthropic", "Other"], 
        default="Gemini"
    )

    env_key_map = {
        "OpenAI": "OPENAI_API_KEY",
        "Gemini": "GEMINI_API_KEY", # LiteLLM uses GEMINI_API_KEY or GOOGLE_API_KEY
        "Anthropic": "ANTHROPIC_API_KEY",
        "Other": "LLM_API_KEY"
    }
    
    env_var_name = env_key_map.get(provider, "LLM_API_KEY")
    api_key = Prompt.ask(f"Enter your [cyan]{env_var_name}[/]", password=True)

    if api_key:
        env_content = f"{env_var_name}={api_key}\n"
        
        # 선택 사항: 기본 모델 설정 (나중에 엔진에서 사용 가능)
        # default_model = Prompt.ask("Default Model Name (optional)", default="gemini/gemini-pro")
        # env_content += f"DENAVY_DEFAULT_MODEL={default_model}\n"

        try:
            env_path.write_text(env_content, encoding="utf-8")
            console.print(f"[green]✔ Successfully created {env_path}[/]")
            console.print(f"[dim]  Key saved as {env_var_name}[/]")
        except Exception as e:
            console.print(f"[red]✘ Failed to write .env: {e}[/]")
    else:
        console.print("[yellow]No API key provided. Skipping .env creation.[/]")

    console.print("\n[bold green]✨ Initialization complete![/]")
    console.print("Try running: [bold white]denavy run[/]")


def _create_directories(dirs: list[str]) -> None:
    for d in dirs:
        path = Path(d)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            console.print(f"[green]✔ Created directory: {d}/[/]")
        else:
            console.print(f"[dim]  Directory exists: {d}/[/]")
