"""Utilities for loading orchestration templates."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, Dict

from denavy_common.exceptions import TemplateLoadError


class TemplateLoader:
    """Loads and validates template TOML files."""

    def __init__(self, templates_dir: Path) -> None:
        self.templates_dir = templates_dir

    def load(self, template_name: str) -> Dict[str, Any]:
        candidate = template_name
        if not candidate.endswith(".toml"):
            candidate = f"{candidate}.toml"

        template_path = self.templates_dir / candidate
        if not template_path.exists():
            raise TemplateLoadError(f"Template '{template_name}' not found under {self.templates_dir}")

        with template_path.open("r", encoding="utf-8") as file_obj:
            content = file_obj.read()
        
        # '진화': 환경 변수 치환 (${VAR} 형식)
        import os
        from string import Template
        
        # os.path.expandvars works but string.Template is more explicit for ${VAR}
        # Using safe_substitute to avoid errors if a var is missing (leaves it as ${VAR})
        content = Template(content).safe_substitute(os.environ)
        
        data = tomllib.loads(content)

        if "template" not in data:
            raise TemplateLoadError("Template missing required 'template' table")

        template = data["template"]
        if "steps" not in template or not isinstance(template["steps"], list):
            raise TemplateLoadError("Template requires a list of 'steps'")

        return data
