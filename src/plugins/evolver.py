"""
Evolver Plugin: Modifies code based on user requests using LLMs.
"""
from __future__ import annotations

import re
import pathlib
from typing import Any, Dict, Optional

from litellm import completion
from rich.console import Console

from denavy_common import BasePlugin, CycleState, PluginExecutionError, PluginResult
from .registry import register_plugin


class EvolverPlugin(BasePlugin):
    name = "evolver"
    description = "Iteratively improves code based on user feedback."

    def __init__(self) -> None:
        self.console = Console()

    def run(self, state: CycleState, config: Dict[str, Any]) -> PluginResult:
        user_input = state.user_input
        if not user_input:
            raise PluginExecutionError("No user_input present in state.")

        # 1. Identify target file
        file_context = state.file_contents or ""
        target_file = self._identify_target_file(user_input, file_context, config)
        
        if not target_file:
             return PluginResult(
                status="error",
                message="Could not identify a target file to edit.",
            )

        # 2. Read file content safely
        try:
            original_content = self._read_file_safely(target_file)
        except FileNotFoundError:
             return PluginResult(
                status="error",
                message=f"Target file not found: {target_file}",
            )

        # 3. Generate solution
        new_content = self._generate_solution(target_file, original_content, user_input, config)
        
        if not new_content:
             return PluginResult(
                status="error",
                message="LLM failed to generate valid code.",
            )

        # 4. Write back (In a real scenario, we might want to propose it first, but here we simulate the 'evolver' action)
        # For safety in this plugin, we might just return it as a proposal or write it. 
        # Given the prompt implies "refactor... to make it production ready", I will assume it should return the proposal 
        # or write it if the architecture supports it. 
        # Looking at `simple_llm_resolver.py`, it returns `proposed_resolution`.
        # However, an 'evolver' usually implies action. 
        # I will return it as `proposed_resolution` and also `output` for the engine to handle.
        
        return PluginResult(
            status="success",
            output={"target_file": target_file, "new_content": new_content},
            proposed_resolution=f"Updated {target_file} with new logic.",
            tags=["evolver", "code-generation"],
            message=f"Evolved {target_file}",
        )

    def _identify_target_file(self, user_input: str, file_context: str, config: Dict[str, Any]) -> str:
        """
        Identifies which file the user wants to modify.
        """
        # Improvement 2: Increase Context Window to 4000
        context_snippet = file_context[:4000]
        
        prompt = (
            f"User Request: {user_input}\n"
            f"File Context (first 4000 chars): {context_snippet}\n\n"
            "Identify the absolute path of the file that needs modification based on the request and context.\n"
            "Return ONLY the file path, nothing else."
        )
        
        model = config.get("model", "gpt-4o-mini")
        
        try:
            response = completion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            path_str = response.choices[0]["message"]["content"].strip()
            # Basic cleanup if LLM wraps in quotes or backticks
            path_str = path_str.strip("'\"`")
            return path_str
        except Exception as e:
            self.console.print(f"[red]Error identifying file: {e}[/red]")
            return ""

    def _generate_solution(self, target_file: str, file_content: str, user_input: str, config: Dict[str, Any]) -> str:
        """
        Generates the new code content using LLM.
        """
        prompt = (
            f"You are an expert Python developer.\n"
            f"Target File: {target_file}\n"
            f"User Request: {user_input}\n\n"
            f"Current Content:\n```python\n{file_content}\n```\n\n"
            "Rewrite the file to satisfy the user request.\n"
            "Output the full valid Python code inside a markdown code block (```python ... ```).\n"
        )
        
        model = config.get("model", "gpt-4o") # Use a stronger model for coding
        
        try:
            response = completion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            raw_content = response.choices[0]["message"]["content"]
            
            # Improvement 1: Fix Markdown Parsing with Regex
            # Look for ```python ... ``` or just ``` ... ```
            # re.DOTALL makes . match newlines
            match = re.search(r"```(?:python)?\s*(.*?)```", raw_content, re.DOTALL)
            if match:
                return match.group(1).strip()
            
            # Fallback: if no code blocks found, check if the whole content looks like code
            # or return raw content if it doesn't look like markdown text.
            # But the requirement was strict regex.
            # If regex fails, it might be that the LLM didn't use blocks.
            # We will log a warning and return raw_content if it looks reasonable, 
            # but for "production-ready" strictness, we might want to return None or empty.
            # Let's return raw_content but warn, or strictly fail. 
            # The user said "current logic fails and corrupts". 
            # So if regex fails, we should probably not return raw text that might contain "Here is the code".
            
            return "" 
            
        except Exception as e:
            self.console.print(f"[red]Error generating solution: {e}[/red]")
            return ""

    def _read_file_safely(self, path: str) -> str:
        """
        Reads a file with safety encoding to prevent crashes.
        """
        # Improvement 3: Safety Encoding
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception as e:
            raise e

register_plugin(EvolverPlugin)
