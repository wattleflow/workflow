# Module name: tests/test_strategy.py
# Tests for the strategy families (FRQ-STR): the method names that carry the intent, `execute` as the
# one abstract method, write answering a bool, every failure carried as StrategyException with its
# cause (a StrategyException from the specialisation passes through unchanged), and the stand-in read.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_strategy -v
import logging
import unittest

from wattleflow.concrete.document import Document
from wattleflow.concrete.exception import StrategyException
from wattleflow.concrete.strategy import (
    Strategy,
    StrategyCreate,
    StrategyGenerate,
    StrategyRead,
    StrategyReadDummy,
    StrategyWrite,
)

QUIET = {"level": logging.CRITICAL}


def build(base, result=None, error=None):
    class Concrete(base):
        calls = []

        def execute(self, caller, **kwargs):
            type(self).calls.append((caller, kwargs))
            if error is not None:
                raise error
            return result

    return Concrete(**QUIET)


class Caller:
    name = "caller"


class ContractTest(unittest.TestCase):
    def test_execute_is_the_only_abstract_method(self):
        for base in (Strategy, StrategyGenerate, StrategyCreate, StrategyRead, StrategyWrite):
            with self.subTest(base=base.__name__):
                self.assertEqual(base.__abstractmethods__, frozenset({"execute"}))

    def test_a_family_without_execute_cannot_be_built(self):
        class NoExecute(StrategyCreate):
            pass

        with self.assertRaises(TypeError):
            NoExecute()

    def test_each_family_forwards_its_arguments_to_execute(self):
        caller = Caller()
        cases = (
            (StrategyGenerate, lambda s: s.generate(caller, k=1), {"k": 1}),
            (StrategyCreate, lambda s: s.create(caller, k=1), {"k": 1}),
            (StrategyRead, lambda s: s.read(caller, "id-1", k=1), {"identifier": "id-1", "k": 1}),
            (StrategyWrite, lambda s: s.write(caller, "facade", k=1), {"facade": "facade", "k": 1}),
        )
        for base, call, expected in cases:
            with self.subTest(base=base.__name__):
                strategy = build(base, result="x")
                call(strategy)
                self.assertEqual(type(strategy).calls, [(caller, expected)])

    def test_the_result_of_execute_is_returned(self):
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

    def test_a_failure_in_execute_is_a_strategy_exception_with_its_cause(self):
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


class StandInReadTest(unittest.TestCase):
    def test_every_call_warns_and_returns_a_declared_stand_in(self):
        strategy = StrategyReadDummy(level=logging.DEBUG)
        with self.assertLogs(level=logging.WARNING) as logged:
            first = strategy.read(Caller(), "doc-1")
            second = strategy.read(Caller(), "doc-2")
        self.assertEqual(len(logged.records), 2)
        metadata = first.request().metadata
        self.assertIs(metadata["implemented"], False)
        self.assertEqual(metadata["declared_by"], "StrategyReadDummy")
        self.assertEqual(metadata["identifier"], "doc-1")
        self.assertEqual(second.request().metadata["identifier"], "doc-2")

    def test_strict_raises_with_the_stand_in_attached(self):
        strategy = StrategyReadDummy(strict=True, **QUIET)
        with self.assertRaises(StrategyException) as caught:
            strategy.read(Caller(), "doc-1")
        self.assertIs(caught.exception.document.request().metadata["implemented"], False)
        self.assertTrue(strategy.strict)

    def test_the_configured_document_type_is_used_when_it_accepts_the_notice(self):
        class Notice(Document[dict]):
            @property
            def size(self):
                return len(self.content)

        facade = StrategyReadDummy(document_type=Notice, **QUIET).read(Caller(), "x")
        self.assertIsInstance(facade.request(), Notice)

    def test_a_type_that_cannot_carry_the_notice_falls_back_to_the_placeholder(self):
        class Strict(Document[dict]):
            def __init__(self, content=None, **kwargs):
                raise TypeError("no mapping content")

        facade = StrategyReadDummy(document_type=Strict, **QUIET).read(Caller(), "x")
        self.assertEqual(type(facade.request()).__name__, "DummyReadDocument")
        self.assertEqual(StrategyReadDummy(document_type=Strict, **QUIET).expected, "Strict")


class SlotsTest(unittest.TestCase):
    def test_only_the_stand_in_holds_state(self):
        self.assertEqual(Strategy.__slots__, ())
        self.assertEqual(set(StrategyReadDummy.__slots__), {"_document_type", "_strict"})


if __name__ == "__main__":
    unittest.main()
