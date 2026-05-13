# Module name: helpers/sanitiser.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Description: This module provides a utility function for sanitising URIs by masking
sensitive credentials such as passwords in connection strings. It ensures
secure handling and logging of URIs within the Wattleflow framework.
"""

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
from urllib.parse import urlparse, urlunparse

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Global methods                                                       #
# --------------------------------------------------------------------------- #


def sanitised_uri(uri: str) -> str:
    parsed = urlparse(uri)
    if parsed.username and parsed.password:
        # Extract host[:port] from netloc directly to preserve original casing.
        # parsed.hostname lowercases the host, which would silently alter the URI.
        host_part = parsed.netloc.rsplit("@", 1)[-1]
        netloc = f"{parsed.username}:***@{host_part}"
        sanitized = parsed._replace(netloc=netloc)
        return urlunparse(sanitized)
    return uri


# --------------------------------------------------------------------------- #
# endregion Global methods                                                    #
# --------------------------------------------------------------------------- #
