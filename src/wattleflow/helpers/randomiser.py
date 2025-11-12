# Module name: randomiser.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


import time
import threading


"""
# Examples:

try:
    R = 4
    print("==>1")
    sf = Snowflake(1)
    for i in range(1, R, 1):
        print(i, sf.execute())
    del sf

    print("==>2")
    for i in range(1, R * 3, 4):
        sf = Snowflake(i)
        print(i, sf.execute())
    del sf
except Exception as e:
    print(str(e))

"""


class Snowflake:

    def __init__(self, node_id: int):
        # 41 bits timestamp, 10 bits node id, 12 bits sequence = 63 bits
        self._epoch = 1609459200000  # custom epoch (ms) e.g. 2021-01-01
        self._node_id_bits = 10
        self._seq_bits = 12
        self._max_node = (1 << self._node_id_bits) - 1
        self._max_seq = (1 << self._seq_bits) - 1

        if not (0 <= node_id <= self._max_node):
            raise ValueError("node_id out of range")

        self._node_id = node_id
        self._sequence = 0
        self._last_ts = -1
        self._lock = threading.Lock()

    def _timestamp(self):
        return int(time.time() * 1000) - self._epoch

    def next_id(self) -> int:
        with self._lock:
            ts = self._timestamp()
            if ts < self._last_ts:
                # clock moved backwards; u real projektu treba bolje rukovanje
                raise RuntimeError("Clock moved backwards")
            if ts == self._last_ts:
                self._sequence = (self._sequence + 1) & self._max_seq
                if self._sequence == 0:
                    # pri velikom prometu čekaj sljedeći ms
                    while ts <= self._last_ts:
                        ts = self._timestamp()
            else:
                self._sequence = 0

            self.last_ts = ts
            return (
                (ts << (self._node_id_bits + self._seq_bits))
                | (self._node_id << self._seq_bits)
                | self._sequence
            )


class Timestamp:
    def __init__(self):
        self.lock = threading.Lock()
        self.counter = 0
        self.last_ts = 0

    def next_id(self) -> int:
        with self.lock:
            ts = int(time.time() * 1000)  # ms
            if ts != self.last_ts:
                self.counter = 0
                self.last_ts = ts
            else:
                self.counter += 1
            return ts * 1000 + self.counter
