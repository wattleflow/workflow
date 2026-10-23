# Module name: telemetry/resources/__init__.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #

from __future__ import annotations

__all__ = [
    "Resource",
    "ResourceCpu",
    "ResourceManager",
    "ResourceMemory",
    "ResourceSnapshot",
    "ResourceStorage",
]


from importlib import import_module
from typing import Any

_EXPORTS: dict[str, str] = {
    "Resource": "base",
    "ResourceSnapshot": "base",
    "ResourceCpu": "cpu",
    "ResourceManager": "manager",
    "ResourceMemory": "memory",
    "ResourceStorage": "storage",
}

def __getattr__(name: str) -> Any:
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f".{module}", __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(__all__)
