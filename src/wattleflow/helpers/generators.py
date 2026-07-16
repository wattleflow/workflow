# Module name: generators.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
This module provides Python generator utilities for use within the Wattleflow
framework. It includes methods for generating numeric sequences and segmented
text streams based on configurable patterns.

Random sample-data generation lives in `wattleflow.helpers.random_data`
(wattleflow-processors) — it is backed by numpy.


Example 1: Generator counter from 1 to a given range
    from wattleflow.helpers.generators import inc, text_generator

    counter = inc()
    for _ in range(5):
        print(next(counter))
    # result: 1, 2, 3, 4, 5

Example 2: Generator split text into sentences

    text = "This is the first sentence. This is the second sentence! And finally third sentence?"
    for part in text_generator(text):
        print(part)
    Result:
    This is the first sentence
    This is the second sentence
    And finally third sentence
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
