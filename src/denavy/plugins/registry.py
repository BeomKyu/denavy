"""Plugin Registry."""

from typing import Type, Dict, Optional
from denavy.domain import BasePlugin

_REGISTRY: Dict[str, Type[BasePlugin]] = {}

def register_plugin(cls: Type[BasePlugin]) -> Type[BasePlugin]:
    _REGISTRY[cls.name] = cls
    return cls

def get_plugin(name: str) -> Optional[Type[BasePlugin]]:
    return _REGISTRY.get(name)

def list_plugins() -> list[str]:
    return list(_REGISTRY.keys())
