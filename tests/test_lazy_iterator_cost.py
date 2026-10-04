# Module name: tests/test_lazy_iterator_cost.py
# Time cost of every method LazyIterator and LazyAsyncIterator define (FRQ-ITR): each is measured as a
# median per call and must stay within a generous budget (it catches an order-of-magnitude regression,
# not a few nanoseconds); the table is printed when WF_TIMING=1.
#
# Run from `workflow/`:
#   WF_TIMING=1 PYTHONPATH=src:../core/src python -m unittest tests.test_lazy_iterator_cost -v
import asyncio
import functools
import os
import statistics
import time
import unittest

from wattleflow.concrete.iterator import LazyAsyncIterator, LazyIterator

BUDGET_NS = 200_000  # median per call; every method measures far below it
REPEATS = 5
LOOPS = 3000


class Endless(LazyIterator):
    def create_iterator(self):
        return iter(range(1_000_000_000))


class AsyncEndless(LazyAsyncIterator):
    def create_iterator(self):
        async def items():
            value = 0
            while True:
                yield value
                value += 1

        return items()


def median(call, loops=LOOPS) -> float:
    runs = []
    for _ in range(REPEATS):
        started = time.perf_counter()
        for _ in range(loops):
            call()
        runs.append((time.perf_counter() - started) / loops * 1e9)
    return statistics.median(runs)


async def async_median(call, loops=LOOPS) -> float:
    runs = []
    for _ in range(REPEATS):
        started = time.perf_counter()
        for _ in range(loops):
            await call()
        runs.append((time.perf_counter() - started) / loops * 1e9)
    return statistics.median(runs)


@functools.cache
def measure() -> dict[str, float]:
    result = {}
    result["LazyIterator.__init__"] = median(Endless)
    result["LazyIterator.__next__ (first fetch, with construction)"] = median(
        lambda: next(Endless())
    )
    warm = Endless()
    next(warm)
    result["LazyIterator.__next__ (later fetch)"] = median(lambda: next(warm), loops=100_000)
    result["LazyAsyncIterator.__init__"] = median(AsyncEndless)

    async def run_async():
        async def first():
            await AsyncEndless().__anext__()

        later = AsyncEndless()
        await later.__anext__()
        return (
            await async_median(first),
            await async_median(later.__anext__, loops=50_000),
        )

    first, later_fetch = asyncio.run(run_async())
    result["LazyAsyncIterator.__anext__ (first fetch, with construction)"] = first
    result["LazyAsyncIterator.__anext__ (later fetch)"] = later_fetch
    return result


class CoverageTest(unittest.TestCase):
    def test_every_defined_method_has_a_timing_case(self):
        defined = {
            f"{owner.__name__}.{name}"
            for owner in (LazyIterator, LazyAsyncIterator)
            for name in ("__init__", "__next__", "__anext__")
            if name in vars(owner)
        }
        measured = {key.split(" ")[0] for key in measure()}
        self.assertEqual(defined - measured, set())


class CostTest(unittest.TestCase):
    results: dict[str, float] = {}

    @classmethod
    def setUpClass(cls):
        cls.results = measure()

    @classmethod
    def tearDownClass(cls):
        if os.environ.get("WF_TIMING"):
            print("\nmedian cost per call (ns), budget", BUDGET_NS)
            for name, value in cls.results.items():
                print(f"  {name:62} {value:10.0f}")

    def test_every_method_stays_within_the_budget(self):
        for name, cost in self.results.items():
            with self.subTest(method=name):
                self.assertLess(cost, BUDGET_NS, f"{name}: {cost:.0f} ns per call")

    def test_a_measured_cost_is_positive(self):
        for name, cost in self.results.items():
            with self.subTest(method=name):
                self.assertGreater(cost, 0)

    def test_a_later_fetch_costs_less_than_the_first_one(self):
        self.assertLess(
            self.results["LazyIterator.__next__ (later fetch)"],
            self.results["LazyIterator.__next__ (first fetch, with construction)"],
        )


if __name__ == "__main__":
    unittest.main()
