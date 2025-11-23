"""Pydantic contracts shared across the Denavy engine and plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Sequence

from pydantic import BaseModel, Field


class CycleState(BaseModel):
    """Mutable state that flows through plugins during a cycle."""

    cycle_id: str
    created_at: datetime
    
    user_input: Optional[str] = None
    file_contents: Optional[str] = None
    proposed_resolution: Optional[str] = None
    user_feedback: Optional[str] = None
    
    scratchpad: Dict[str, Any] = Field(default_factory=dict)
    
    notes: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)

    def set_scratchpad(self, key: str, value: Any) -> None:
        """임시/사용자 정의 데이터를 스크래치패드에 저장합니다."""
        self.scratchpad[key] = value

    def get_scratchpad(self, key: str, default: Any = None) -> Any:
        """스크래치패드에서 임시/사용자 정의 데이터를 조회합니다."""
        return self.scratchpad.get(key, default)

    def add_note(self, note: str) -> None:
        self.notes.append(note)

    def add_tags(self, tags: Sequence[str]) -> None:
        for tag in tags:
            if tag not in self.tags:
                self.tags.append(tag)


class EventLogEntry(BaseModel):
    """Immutable record describing an executed plugin step."""

    timestamp: datetime
    cycle_id: str
    plugin: str
    status: Literal["success", "error"]
    input_payload: Dict[str, Any] = Field(default_factory=dict)
    output_payload: Dict[str, Any] = Field(default_factory=dict)
    message: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class SummaryDocument(BaseModel):
    """Structured summary derived from a cycle's raw events."""

    cycle_id: str
    generated_at: datetime
    headline: str
    highlights: List[str] = Field(default_factory=list)
    action_items: List[str] = Field(default_factory=list)
    raw_text: str = ""


class IndexRecord(BaseModel):
    """Compact index entry to speed up exploration across cycles."""

    cycle_id: str
    created_at: datetime
    headline: str
    tags: List[str] = Field(default_factory=list)
    summary_url: Optional[str] = None


class PluginResult(BaseModel):
    """Return payload that plugins hand back to the engine."""

    status: Literal["success", "error"] = "success"
    output: Dict[str, Any] = Field(default_factory=dict)
    
    user_input: Optional[str] = None
    file_contents: Optional[str] = None
    proposed_resolution: Optional[str] = None
    user_feedback: Optional[str] = None
    
    scratchpad_updates: Dict[str, Any] = Field(default_factory=dict)

    tags: List[str] = Field(default_factory=list)
    message: Optional[str] = None


class JudgeDecision(BaseModel):
    """Decision returned by the veto LLM before executing a template."""

    approved: bool
    reason: str
    recommended_template: Optional[str] = None
    confidence_score: float = 0.0
    raw_response: Optional[Any] = None


class PluginConfig(BaseModel):
    """Configuration section for a template-defined plugin step."""

    plugin: str
    config: Dict[str, Any] = Field(default_factory=dict)


class BasePlugin(ABC):
    """Interface that all orchestrated plugins must respect."""

    name: str
    description: str = ""

    @abstractmethod
    def run(self, state: CycleState, config: Dict[str, Any]) -> PluginResult:
        """Execute plugin logic using the mutable cycle state."""

    def supports_dynamic_invocation(self) -> bool:
        """Flag dynamic-mode compatibility for discovery tooling."""

        return True
    
class PluginExecutionError(Exception):
    """Custom exception for plugins to signal a critical failure."""

class JudgeConfig(BaseModel):
    """Configuration for the VetoEngine (Judge)."""
    model: str
    system_prompt: Optional[str] = None
    temperature: float = 0.0


class SummaryConfig(BaseModel):
    """Configuration for the final summarizer step."""
    plugin: str
    config: Dict[str, Any] = Field(default_factory=dict)


class Template(BaseModel):
    """Pydantic model for a .toml template file."""
    name: str
    description: str = ""
    judge: Optional[JudgeConfig] = None
    steps: List[PluginConfig] = Field(default_factory=list)
    summary: Optional[SummaryConfig] = None