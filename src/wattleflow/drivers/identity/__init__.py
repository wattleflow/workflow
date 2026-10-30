# Module name: drivers/identity/__init__.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""The identity driver and its algorithms (SyRS-DRV-identity)."""

from __future__ import annotations

__all__ = ["DriverIdentity", "Identity", "Result"]

from wattleflow.drivers.identity.driver import DriverIdentity, Identity, Result
