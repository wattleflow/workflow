# Module name: helpers/resources/__init__.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

# --------------------------------------------------------------------------- #
# Lazy public API (PEP 562) — DR-WFL-007.
#
# One resource per module, so adding one is adding a file rather than growing a
# class. The package carries an `__init__.py` to belong to THIS distribution and
# not merge with a same-named directory another ships (CLAUDE.md 2.6, 2.7 t.1,
# DR-WFL-017). Nothing here needs an optional library today; the deferred form is
# kept because the GPU resource that will join arrives from a distribution that
# does (`HLRQ-18` BR-08).
# --------------------------------------------------------------------------- #

from __future__ import annotations

from importlib import import_module
from typing import Any

# Public name -> defining submodule. The single declaration of what this package
# exposes and from where; extend it when a resource is added.
_EXPORTS: dict[str, str] = {
    "Resource": "base",
    "ResourceSnapshot": "base",
    "ResourceCpu": "cpu",
    "ResourceManager": "manager",
    "ResourceMemory": "memory",
    "ResourceStorage": "storage",
}

__all__ = [
    "Resource",
    "ResourceCpu",
    "ResourceManager",
    "ResourceMemory",
    "ResourceSnapshot",
    "ResourceStorage",
]


def __getattr__(name: str) -> Any:  # NFRQ-ORG-11: pep562
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f".{module}", __name__), name)
    globals()[name] = value  # resolve once; subsequent lookups skip __getattr__
    return value


def __dir__() -> list[str]:  # NFRQ-ORG-11: pep562
    return sorted(__all__)
