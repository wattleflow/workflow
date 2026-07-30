# Module name: generators.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""Numeric sequence and sentence-splitting generators.

Random sample-data generation lives in wattleflow-processors (numpy-backed).
"""


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
import re

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Global methods                                                       #
# --------------------------------------------------------------------------- #


def inc(start: int = 0):
    number = start
    while True:
        number += 1
        yield number


def text_generator(text, pattern=r"(?<=[.!?])\s+", stopper=None):
    parts = re.split(pattern, text)
    for i, part in enumerate(parts):
        if stopper and stopper == i:
            break
        yield part.strip()


# --------------------------------------------------------------------------- #
# endregion Global methods                                                   #
# --------------------------------------------------------------------------- #
