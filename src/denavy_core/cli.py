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

from .engine import ExecutionEngine
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
    engine = ExecutionEngine(templates_dir=templates_dir, logs_dir=logs_dir, console=console)
    engine.run(template_name=template, cycle_id=cycle_id)


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



@app.command()
def auto(
    request: str = typer.Argument(..., help="Natural language request describing what you want to do"),
    templates_dir: Path = typer.Option(Path("templates"), "--templates-dir", help="Directory containing templates"),
    logs_dir: Path = typer.Option(Path("logs"), "--logs-dir", help="Directory where logs are written"),
) -> None:
    """Auto-select and run the best template for your request."""
    console.print(Panel(f"🤖 Auto-Pilot: Analyzing request... '{request}'", style="bold purple"))

    # 1. Scan Templates
    templates = _scan_templates(templates_dir)
    if not templates:
        console.print("[red]No templates found![/]")
        raise typer.Exit(code=1)

    # 2. AI Routing
    try:
        selected_template_name = _route_request(request, templates)
    except Exception as e:
        console.print(f"[red]Routing failed: {e}[/]")
        raise typer.Exit(code=1)

    console.print(f"[green]✔ Selected Template: [bold]{selected_template_name}[/][/]")

    # 3. Execute
    engine = ExecutionEngine(templates_dir=templates_dir, logs_dir=logs_dir, console=console)
    engine.run(template_name=selected_template_name)


def _create_directories(dirs: list[str]) -> None:
    for d in dirs:
        path = Path(d)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            console.print(f"[green]✔ Created directory: {d}/[/]")
        else:
            console.print(f"[dim]  Directory exists: {d}/[/]")


def _scan_templates(templates_dir: Path) -> list[dict]:
    """Scans .toml files and extracts metadata."""
    import tomllib
    
    templates = []
    if not templates_dir.exists():
        return []

    for file_path in templates_dir.glob("*.toml"):
        try:
            with file_path.open("rb") as f:
                data = tomllib.load(f)
                meta = data.get("template", {})
                name = meta.get("name", file_path.stem)
                desc = meta.get("description", "No description provided.")
                # We use the filename (stem) as the ID for execution, but 'name' for display/routing if needed.
                # Actually orchestrator.run takes the filename stem usually, or the name defined in TOML?
                # cli.py run command uses `template` arg which defaults to "default_template".
                # TemplateLoader loads by filename. So we should return the filename stem as the key.
                templates.append({
                    "id": file_path.stem,
                    "name": name,
                    "description": desc
                })
        except Exception as e:
            console.print(f"[yellow]Warning: Failed to parse {file_path}: {e}[/]")
    
    return templates


def _route_request(user_request: str, templates: list[dict]) -> str:
    """Uses LLM to select the best template."""
    import litellm
    import os

    # Simple prompt construction
    options_text = "\n".join([f"- {t['id']}: {t['description']}" for t in templates])
    
    prompt = f"""
    User Request: "{user_request}"

    Available Templates:
    {options_text}

    Task: Select the most appropriate template ID for this request.
    Return ONLY the template ID (e.g., 'default_template'). Do not add any explanation.
    """

    # Use a cheap/fast model for routing if possible, or default to env var
    model = os.getenv("DENAVY_ROUTER_MODEL", "gemini/gemini-2.5-flash-lite")

    response = litellm.completion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0
    )
    
    selected_id = response.choices[0].message.content.strip()
    
    # Basic validation
    valid_ids = {t['id'] for t in templates}
    if selected_id not in valid_ids:
        # Fallback: try to find a partial match or default
        for vid in valid_ids:
            if vid in selected_id:
                return vid
        raise ValueError(f"LLM returned invalid template ID: {selected_id}")

    return selected_id


if __name__ == "__main__":
    app()
