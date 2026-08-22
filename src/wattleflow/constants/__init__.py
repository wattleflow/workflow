# Module name: constants/__init__.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

# What the framework itself raises; the enumerated vocabulary lives in
# `wattleflow.enums`, the vocabulary only specialisations read ships with
# wattleflow-processors (DR-WFL-016).

from . import errors
from .errors import *  # noqa: F403

__all__ = [
    *errors.__all__,
]
