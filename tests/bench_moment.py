# Module name: tests/bench_moment.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence
"""Cost of Moment and its aware and naive helpers, extrapolated to N records. Standard library only.

Run: PYTHONPATH=src:../core/src python tests/bench_moment.py [scalar_sample=200000]
     [column_sample=3000000] [total=550000000]
A measurement, not a test: unittest discovery does not collect it (no `test_` prefix).
"""

import math
import random
import sys
import time
import tracemalloc
from array import array
from datetime import datetime, timezone

from wattleflow.helpers.moment import Moment, MomentAwareHelper as A, MomentNaiveHelper as N

NS = int(sys.argv[1]) if len(sys.argv) > 1 else 200_000
NC = int(sys.argv[2]) if len(sys.argv) > 2 else 3_000_000
TOTAL = int(sys.argv[3]) if len(sys.argv) > 3 else 550_000_000


def best(f, rep=3):
    runs = []
    for _ in range(rep):
        t = time.perf_counter()
        f()
        runs.append(time.perf_counter() - t)
    return min(runs)


def fmt(sec):
    return (
        f"{sec:8.0f} s"
        if sec < 600
        else f"{sec / 60:7.1f} min"
        if sec < 7200
        else f"{sec / 3600:6.2f} h"
    )


random.seed(1)
ns_list = [random.randrange(1_500_000_000 * 10**9, 1_900_000_000 * 10**9) for _ in range(NS)]
wall_list = [n // 1000 * 1000 for n in ns_list]
ms = [Moment(n, True) for n in ns_list]
nms = [Moment(n, False) for n in wall_list]
dts = [A.to_datetime(m) for m in ms]
ndts = [N.to_datetime(m) for m in nms]
isos = [A.to_iso(m) for m in ms]
bs = [A.to_bytes(m) for m in ms]

ops = {
    "(empty loop)": lambda: [n for n in ns_list],
    "Moment(ns, True)": lambda: [Moment(n, True) for n in ns_list],
    "A.from_unix_ns(ns)": lambda: [A.from_unix_ns(n) for n in ns_list],
    "A.moment(datetime)": lambda: [A.moment(d) for d in dts],
    "A.from_iso(str)": lambda: [A.from_iso(s) for s in isos],
    "A.from_bytes(bytes)": lambda: [A.from_bytes(b) for b in bs],
    "A.to_datetime(Moment)": lambda: [A.to_datetime(m) for m in ms],
    "A.to_datetime(int)": lambda: [A.to_datetime(n) for n in ns_list],
    "A.to_datetime(m, 'Australia/Sydney')": lambda: [
        A.to_datetime(m, "Australia/Sydney") for m in ms
    ],
    "A.to_iso(Moment)": lambda: [A.to_iso(m) for m in ms],
    "A.to_iso(int)": lambda: [A.to_iso(n) for n in ns_list],
    "A.to_str(m, '%Y-%m-%d')": lambda: [A.to_str(m, "%Y-%m-%d") for m in ms],
    "A.to_unix_ns(Moment)": lambda: [A.to_unix_ns(m) for m in ms],
    "A.to_unix_ns(int)": lambda: [A.to_unix_ns(n) for n in ns_list],
    "A.to_bytes(Moment)": lambda: [A.to_bytes(m) for m in ms],
    "A.strip(m, 'Australia/Sydney') -> naive": lambda: [A.strip(m, "Australia/Sydney") for m in ms],
    "A.strip(int, 'Australia/Sydney')": lambda: [A.strip(n, "Australia/Sydney") for n in ns_list],
    "N.moment(datetime)": lambda: [N.moment(d) for d in ndts],
    "N.to_datetime(int)": lambda: [N.to_datetime(n) for n in wall_list],
    "N.to_iso(int)": lambda: [N.to_iso(n) for n in wall_list],
    "a < b": lambda: [a < b for a, b in zip(ms, ms, strict=True)],
    "[baseline] datetime.fromisoformat": lambda: [datetime.fromisoformat(s) for s in isos],
    "[baseline] dt.isoformat()": lambda: [d.isoformat() for d in dts],
}

loop = None
print(f"Sample scalar={NS:,}  column={NC:,}  extrapolated to {TOTAL:,}\n")
print(f"{'operation':42s}{'ns/record':>10s}{'x' + format(TOTAL, ',').replace(',', ' '):>16s}")
for name, f in ops.items():
    per = best(f) / NS
    if name.startswith("(empty"):
        loop = per
    print(f"{name:42s}{per * 1e9:10.0f}{fmt(per * TOTAL):>16s}")
print(
    f"\n(the loop's {loop * 1e9:.0f} ns/record is in every row; the operation alone = row - loop)"
)

# ---- memory per object (with its own int) ----
tracemalloc.start()
b0 = tracemalloc.get_traced_memory()[0]
objs = [Moment((n + 1) - 1, True) for n in ns_list[:100_000]]
b1 = tracemalloc.get_traced_memory()[0]
per_obj = (b1 - b0) / 100_000
objs2 = [datetime.fromtimestamp(n / 1e9, timezone.utc) for n in ns_list[:100_000]]
b2 = tracemalloc.get_traced_memory()[0]
per_dt = (b2 - b1) / 100_000
tracemalloc.stop()
del objs, objs2

print("\nMEMORY per record (measured with tracemalloc) ->", f"{TOTAL:,}")
for n, b in [("array('q') column", 8), ("Moment object + its int", per_obj + 8),
             ("datetime object (+ pointer)", per_dt + 8)]:  # fmt: skip
    print(f"  {n:28s}{b:7.0f} B   {b * TOTAL / 1e9:8.1f} GB")

# ---- int64 column ----
chunk = (ns_list * (NC // NS + 1))[:NC]
t_build = best(lambda: array("q", chunk), 2)
col = array("q", chunk)
t_bytes = best(lambda: col.tobytes(), 3)
raw = col.tobytes()
t_from = best(lambda: array("q").frombytes(raw), 3)
t_scan = best(lambda: sum(1 for x in col if 1_600_000_000 * 10**9 <= x < 1_700_000_000 * 10**9), 2)
t_sort = best(lambda: sorted(col), 1)

print("\nCOLUMN array('q'), time per record -> extrapolated")
column_ops = [
    ("build from a list of Python ints", t_build),
    ("tobytes() (write)", t_bytes),
    ("frombytes() (read)", t_from),
    ("filter by range (pure Python)", t_scan),
]
for n, t in column_ops:
    print(f"  {n:40s}{t / NC * 1e9:8.1f} ns   {fmt(t / NC * TOTAL):>12s}")
fac = (TOTAL / NC) * (math.log2(TOTAL) / math.log2(NC))
label = "sorted() pure Python (n log n)"
print(f"  {label:40s}{t_sort / NC * 1e9:8.1f} ns   {fmt(t_sort * fac):>12s}")
