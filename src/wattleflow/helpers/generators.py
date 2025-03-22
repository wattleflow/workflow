# Module Name: helpers/generators.py
# Description: This modul contains python generator methods.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence

import re
import numpy as np

records = lambda n: np.random.rand(n)


def inc():
    number = 0
    while True:
        number += 1
        yield number


def text_generator(text, pattern=r"(?<=[.!?])\s+", stopper=None):
    parts = re.split(pattern, text)
    for i, part in enumerate(parts):
        if stopper and stopper == i:
            break
        yield part.strip()
