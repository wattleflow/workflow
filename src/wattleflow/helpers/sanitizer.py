# Module Name: helpers/sanitizer.py
# Description: This modul contains sanitiser helper methods.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence

from urllib.parse import urlparse, urlunparse


def sanitized_uri(uri: str) -> str:
    parsed = urlparse(uri)
    if parsed.username and parsed.password:
        netloc = f"{parsed.username}:***@{parsed.hostname}"
        if parsed.port:
            netloc += f":{parsed.port}"
        sanitized = parsed._replace(netloc=netloc)
        return urlunparse(sanitized)
    return uri
