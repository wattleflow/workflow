# Module name: generators.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
This module provides Python generator utilities for use within the Wattleflow
framework. It includes methods for generating numeric sequences, random data
records, and segmented text streams based on configurable patterns.


Example 1: Generator counter from 1 to a given range
    from wattleflow.helpers.generators import inc, text_generator, records

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
    This is the second sentence! And finally third sentence
    This is the second sentence! And finally third sentence

Example 3: Generate randomm values
    data = records(5)
    print(data)

    Result:
    List of 5 random numbers between 0 and 1
"""


from __future__ import annotations
import re
import numpy as np

records = lambda n: np.random.rand(n)


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
