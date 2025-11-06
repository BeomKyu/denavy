"""Utilities for loading orchestration templates."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, Dict

from denavy_common import TemplateLoadError


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

        with template_path.open("rb") as file_obj:
            data = tomllib.load(file_obj)

        if "template" not in data:
            raise TemplateLoadError("Template missing required 'template' table")

        template = data["template"]
        if "steps" not in template or not isinstance(template["steps"], list):
            raise TemplateLoadError("Template requires a list of 'steps'")

        return data
