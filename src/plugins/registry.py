"""Simple plugin registry used by the engine."""

from __future__ import annotations

import importlib.util
import pathlib
from typing import Dict, Iterable, Optional, Type

from denavy_common import BasePlugin

_PLUGIN_REGISTRY: Dict[str, Type[BasePlugin]] = {}
_PLUGINS_LOADED = False  # 1. 플러그인이 로드되었는지 확인하는 플래그


def _load_all_plugins() -> None:
    """Dynamically scan and import all plugins from the 'plugins' directory."""
    global _PLUGINS_LOADED, _PLUGIN_REGISTRY
    if _PLUGINS_LOADED:
        return

    plugin_dir = pathlib.Path(__file__).parent
    
    for path in plugin_dir.glob("*.py"):
        # __init__.py 또는 _private.py 같은 파일은 무시
        if path.name.startswith(("_", ".")) or path.name == "__init__.py":
            continue

        # 2. 'plugins.my_plugin' 같은 모듈 이름을 만듭니다.
        module_name = f"plugins.{path.stem}"
        
        try:
            # 3. 파일 경로로부터 모듈을 '수동'으로 임포트합니다.
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                # 이 과정에서 모듈 파일 하단의 'register_plugin()'이 실행됩니다.
        except Exception as e:
            print(f"[WARN] Failed to load plugin {path.name}: {e}")

    _PLUGINS_LOADED = True


def register_plugin(plugin_cls: Type[BasePlugin]) -> None:
    _PLUGIN_REGISTRY[plugin_cls.name] = plugin_cls


def get_plugin(name: str) -> Optional[BasePlugin]:
    # 4. 'import plugins' 대신 '자동 스캔' 함수를 호출합니다.
    if not _PLUGINS_LOADED:
        _load_all_plugins()
        
    plugin_cls = _PLUGIN_REGISTRY.get(name)
    if not plugin_cls:
        return None
    return plugin_cls()


def list_plugins() -> Iterable[str]:
    # 5. 'import plugins' 대신 '자동 스캔' 함수를 호출합니다.
    if not _PLUGINS_LOADED:
        _load_all_plugins()
        
    return sorted(_PLUGIN_REGISTRY.keys())
