# Module name: decorators/__init__.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

# Eager aggregate (CLAUDE.md §2.7): both modules resolve inside the clean core
# tier, so importing a name pulls in nothing third-party.

from . import (
    file,
    preset,
)
from .file import *  # noqa: F403
from .preset import *  # noqa: F403

__all__ = [
    *file.__all__,
    *preset.__all__,
]
