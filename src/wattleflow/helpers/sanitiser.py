# Module name: helpers/sanitiser.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Description: This module provides URL sanitising for the Wattleflow framework:
masking credentials in connection strings for readable logs (``mask``) and
reducing a URL, list or mapping of addresses to text that is safe for ``repr``
and audit records (``redact``) (NFRQ-SCR-10 c.3, NFRQ-SCR-18 c.5).
"""

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations

__all__ = ["UrlSanitiser"]

from typing import Any
from urllib.parse import urlparse, urlunparse

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Classes                                                              #
# --------------------------------------------------------------------------- #


class UrlSanitiser:
    KEEP = ("host", "port", "scheme", "url_prefix")

    @staticmethod
    def _host_part(netloc: str) -> str:
        return netloc.rsplit("@", 1)[-1]

    @classmethod
    def mask(cls, uri: str) -> str:
        """``uri`` with the password replaced by ``***``; user name, query and fragment stay.
        For readable logs only. Use ``redact`` for audit records.
        """
        parsed = urlparse(uri)
        if parsed.username and parsed.password:
            netloc = f"{parsed.username}:***@{cls._host_part(parsed.netloc)}"
            return urlunparse(parsed._replace(netloc=netloc))
        return uri

    @classmethod
    def redact(cls, value: Any) -> Any:
        """Reduced to ``scheme://host:port/path``.
        ``value`` without user name, password, query or fragment.
        (``host``, ``port``, ``scheme``, ``url_prefix``).
        """
        if isinstance(value, str):
            parsed = urlparse(value)
            if not (parsed.username or parsed.password or parsed.query or parsed.fragment):
                return value
            return urlunparse(parsed._replace(netloc=cls._host_part(parsed.netloc), query="", fragment=""))
        if isinstance(value, (list, tuple)):
            return [cls.redact(item) for item in value]
        if isinstance(value, dict):
            return {k: v for k, v in value.items() if k in cls.KEEP}
        return f"<{type(value).__name__}>"


# --------------------------------------------------------------------------- #
# endregion Classes                                                           #
# --------------------------------------------------------------------------- #
