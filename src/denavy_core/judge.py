"""The Veto Judge component."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from denavy_common import (
    CycleState,
    JudgeDecision,
    PluginConfig,
    Template,
)
from plugins.registry import list_plugins

from .llm import VetoEngine


class Judge:
    """Evaluates templates and execution plans using an LLM."""

    def __init__(self, templates_dir: Path) -> None:
        self.templates_dir = templates_dir

    def evaluate_template(self, template: Template, state: CycleState) -> JudgeDecision:
        """Decide whether to execute a given template based on the current state."""
        if template.judge is None:
            return JudgeDecision(approved=True, reason="No judge configured; auto-approving.")

        veto_engine = VetoEngine(
            model=template.judge.model,
            system_prompt=template.judge.system_prompt,
            **template.judge.model_dump(exclude={"model", "system_prompt"}),
        )

        plan_prompt = self._render_plan_prompt(template.steps, state)
        decision_dict = veto_engine.decide(plan_prompt)
        return JudgeDecision.model_validate(decision_dict)

    def _render_plan_prompt(self, steps: list[PluginConfig], state: CycleState) -> str:
        """Construct the prompt for the Judge LLM."""
        plan_steps = "\n".join(f"- Step: {step.plugin}" for step in steps)
        discomfort = state.user_input

        prompt_parts = [
            "Review the user's discomfort (if any) and the proposed execution plan."
        ]

        if discomfort:
            prompt_parts.append(f"\nUser Discomfort:\n'''\n{discomfort}\n'''")
        else:
            prompt_parts.append("\nUser Discomfort: (None - Input not provided yet)")

        prompt_parts.append(f"\nProposed Plan:\n{plan_steps}")

        prompt_parts.append(self._get_registry_menu())

        return "\n".join(prompt_parts)

    def _get_registry_menu(self) -> str:
        """Generate a menu of available templates and plugins."""
        menu_lines = ["\nAvailable Tools (Menu):"]

        # 1. Templates
        menu_lines.append("- Templates:")
        for path in self.templates_dir.glob("*.toml"):
             menu_lines.append(f"  * {path.stem}")

        # 2. Plugins
        menu_lines.append("- Plugins:")
        for name in list_plugins():
            menu_lines.append(f"  * {name}")

        return "\n".join(menu_lines)
