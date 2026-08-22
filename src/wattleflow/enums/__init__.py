# Module name: enums/__init__.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

# Eager aggregate (CLAUDE.md §2.7): both modules are stdlib-only, so the masking
# test cannot fail and deferred resolution would buy nothing.

from . import (
    event,
    operation,
)
from .event import *  # noqa: F403
from .operation import *  # noqa: F403

__all__ = [
    *event.__all__,
    *operation.__all__,
]
