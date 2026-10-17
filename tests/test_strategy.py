# Module name: tests/test_strategy.py
# Tests for the strategy families (SyRS-STR-strategy): the method names that carry the intent, `algorithm` as the
# one abstract method, write answering a bool, every failure carried as StrategyException with its
# cause (a StrategyException from the specialisation passes through unchanged).
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_strategy -v
import logging
import unittest

from wattleflow.concrete.exception import StrategyException
from wattleflow.concrete.strategy import (
    Strategy,
    StrategyCreate,
    StrategyGenerate,
    StrategyRead,
    StrategyWrite,
)

QUIET = {"level": logging.CRITICAL}


def build(base, result=None, error=None):
    class Concrete(base):
        calls = []

        def algorithm(self, caller, **kwargs):
            type(self).calls.append((caller, kwargs))
            if error is not None:
                raise error
            return result

    return Concrete(**QUIET)


class Caller:
    name = "caller"


class ContractTest(unittest.TestCase):
    def test_algorithm_is_the_only_abstract_method(self):
        for base in (Strategy, StrategyGenerate, StrategyCreate, StrategyRead, StrategyWrite):
            with self.subTest(base=base.__name__):
                self.assertEqual(base.__abstractmethods__, frozenset({"algorithm"}))

    def test_a_family_without_algorithm_cannot_be_built(self):
        class NoAlgorithm(StrategyCreate):
            pass

        with self.assertRaises(TypeError):
            NoAlgorithm()

    def test_each_family_forwards_its_arguments_to_algorithm(self):
        caller = Caller()
        cases = (
            (StrategyGenerate, lambda s: s.generate(caller, k=1), {"k": 1}),
            (StrategyCreate, lambda s: s.create(caller, k=1), {"k": 1}),
            (StrategyRead, lambda s: s.read(caller, "id-1", k=1), {"identifier": "id-1", "k": 1}),
            (
                StrategyWrite,
                lambda s: s.write(caller, "facade", k=1),
                {"facade": "facade", "k": 1},
            ),
        )
        for base, call, expected in cases:
            with self.subTest(base=base.__name__):
                strategy = build(base, result="x")
                call(strategy)
                self.assertEqual(type(strategy).calls, [(caller, expected)])

    def test_the_result_of_algorithm_is_returned(self):
        caller = Caller()
        self.assertEqual(build(StrategyCreate, result="made").create(caller), "made")
        self.assertEqual(build(StrategyRead, result="doc").read(caller, "id"), "doc")
        self.assertIsNone(build(StrategyGenerate, result=None).generate(caller))


class WriteResultTest(unittest.TestCase):
    def test_write_answers_a_bool(self):
        caller = Caller()
        for result, expected in ((True, True), (False, False), (None, False)):
            with self.subTest(result=result):
                self.assertIs(build(StrategyWrite, result=result).write(caller, "f"), expected)


class FailureTest(unittest.TestCase):
    CASES = (
        ("generate", StrategyGenerate, lambda s, c: s.generate(c)),
        ("create", StrategyCreate, lambda s, c: s.create(c)),
        ("read", StrategyRead, lambda s, c: s.read(c, "id")),
        ("write", StrategyWrite, lambda s, c: s.write(c, "f")),
    )

    def test_a_failure_in_algorithm_is_a_strategy_exception_with_its_cause(self):
        for operation, base, call in self.CASES:
            with self.subTest(operation=operation):
                strategy = build(base, error=ValueError("source down"))
                with self.assertRaises(StrategyException) as caught:
                    call(strategy, Caller())
                self.assertIsInstance(caught.exception.__cause__, ValueError)
                text = str(caught.exception)
                for part in ("Concrete", operation, "source down"):
                    self.assertIn(part, text)

    def test_a_strategy_exception_from_the_specialisation_is_not_wrapped_again(self):
        own = StrategyException(caller=None, error="already carried")
        for operation, base, call in self.CASES:
            with self.subTest(operation=operation):
                strategy = build(base, error=own)
                with self.assertRaises(StrategyException) as caught:
                    call(strategy, Caller())
                self.assertIs(caught.exception, own)

    def test_the_failure_is_traced_at_debug_and_never_above(self):
        strategy = build(StrategyCreate, error=ValueError("down"))
        strategy.set_level(logging.DEBUG)
        with self.assertLogs(level=logging.DEBUG) as logged, self.assertRaises(StrategyException):
            strategy.create(Caller())
        self.assertEqual({r.levelno for r in logged.records} - {logging.DEBUG}, set())


class SlotsTest(unittest.TestCase):
    def test_the_base_strategy_holds_no_state(self):
        self.assertEqual(Strategy.__slots__, ())


if __name__ == "__main__":
    unittest.main()
