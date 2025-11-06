"""Simple plugin registry used by the engine."""

from __future__ import annotations

from typing import Dict, Iterable, Optional, Type

from denavy_common import BasePlugin

_PLUGIN_REGISTRY: Dict[str, Type[BasePlugin]] = {}


def register_plugin(plugin_cls: Type[BasePlugin]) -> None:
    _PLUGIN_REGISTRY[plugin_cls.name] = plugin_cls


def get_plugin(name: str) -> Optional[BasePlugin]:
    if not _PLUGIN_REGISTRY:
        import plugins  # noqa: F401  # lazy import to populate registry
    plugin_cls = _PLUGIN_REGISTRY.get(name)
    if not plugin_cls:
        return None
    return plugin_cls()


def list_plugins() -> Iterable[str]:
    if not _PLUGIN_REGISTRY:
        import plugins  # noqa: F401
    return sorted(_PLUGIN_REGISTRY.keys())
