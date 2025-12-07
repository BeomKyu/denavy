"""Domain models and interfaces for Denavy."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


# --- State & Logging ---

class CycleState(BaseModel):
    """Mutable state passed through the execution cycle."""
    cycle_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Core communication slots
    user_input: Optional[str] = None
    user_feedback: Optional[str] = None

    # Data slots
    file_contents: Optional[str] = None
    proposed_resolution: Optional[str] = None # Often used for generated code/text

    # Flexible storage
    scratchpad: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)

    def update(self, result: 'PluginResult') -> None:
        """Merge a plugin result into the state."""
        if result.user_input is not None: self.user_input = result.user_input
        if result.file_contents is not None: self.file_contents = result.file_contents
        if result.proposed_resolution is not None: self.proposed_resolution = result.proposed_resolution
        if result.user_feedback is not None: self.user_feedback = result.user_feedback

        self.scratchpad.update(result.scratchpad_updates)
        for tag in result.tags:
            if tag not in self.tags:
                self.tags.append(tag)


class EventLog(BaseModel):
    """Immutable record of an execution step."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    cycle_id: str
    plugin: str
    status: Literal["success", "error"]
    message: Optional[str] = None
    input_config: Dict[str, Any] = Field(default_factory=dict)
    output: Dict[str, Any] = Field(default_factory=dict)
    duration_ms: float = 0.0


# --- Plugins ---

class PluginResult(BaseModel):
    """Result returned by a plugin."""
    status: Literal["success", "error"] = "success"
    message: Optional[str] = None
    output: Dict[str, Any] = Field(default_factory=dict) # Structured output data

    # State updates
    user_input: Optional[str] = None
    file_contents: Optional[str] = None
    proposed_resolution: Optional[str] = None
    user_feedback: Optional[str] = None
    scratchpad_updates: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)


class BasePlugin(ABC):
    """Abstract base class for all plugins."""
    name: str
    description: str = ""

    @abstractmethod
    def run(self, state: CycleState, config: Dict[str, Any]) -> PluginResult:
        """Execute the plugin logic."""
        pass


# --- Templates & Configuration ---

class PluginConfig(BaseModel):
    """Configuration for a single step in a plan."""
    plugin: str
    config: Dict[str, Any] = Field(default_factory=dict)


class JudgeConfig(BaseModel):
    """Configuration for the Veto Judge."""
    model: str = "gpt-4-turbo"
    system_prompt: Optional[str] = None
    temperature: float = 0.0


class Template(BaseModel):
    """Definition of an execution workflow."""
    name: str
    description: str = ""
    judge: Optional[JudgeConfig] = None
    steps: List[PluginConfig] = Field(default_factory=list)


# --- Decisions ---

class JudgeDecision(BaseModel):
    """Output from the Judge."""
    approved: bool
    reason: str
    recommended_template: Optional[str] = None
