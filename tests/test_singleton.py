# Module name: tests/test_singleton.py
# Tests for Singleton (FRQ-SGT): one instance per concrete class, abstract classes never cached,
# __init__ once (also under threads, and nobody sees a half-built object), arguments of later calls
# reported rather than lost, a failed __init__ retried, and subclasses with __slots__ without ceremony.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_singleton -v
import threading
import time
import unittest
import warnings
from abc import abstractmethod

from wattleflow.concrete.singleton import Singleton

THREADS = 8


def fresh(**members):
    """A new concrete singleton class per test: `_instances` is keyed by class."""
    return type("Sample", (Singleton,), members)


class IdentityTest(unittest.TestCase):
    def test_two_calls_give_the_same_object(self):
        Sample = fresh()
        self.assertIs(Sample(), Sample())

    def test_each_subclass_has_its_own_instance_and_its_own_lock(self):
        First, Second = fresh(), fresh()
        self.assertIsNot(First(), Second())
        self.assertIsNot(First._lock, Second._lock)
        self.assertIsNot(First._lock, Singleton._lock)

    def test_a_subclass_of_a_subclass_is_a_separate_singleton(self):
        Parent = fresh()
        Child = type("Child", (Parent,), {})
        self.assertIsNot(Parent(), Child())
        self.assertIs(Child(), Child())

    def test_an_abstract_class_is_never_cached(self):
        class Abstract(Singleton):
            @abstractmethod
            def work(self): ...

        self.assertNotIn(Abstract, Singleton._instances)

    def test_a_concrete_subclass_of_an_abstract_one_is_cached(self):
        from abc import ABC

        class Base(Singleton, ABC):
            @abstractmethod
            def work(self): ...

        class Concrete(Base):
            def work(self):
                return 1

        self.assertIs(Concrete(), Concrete())

    def test_name_str_and_repr(self):
        Sample = fresh()
        sample = Sample()
        self.assertEqual((sample.name, str(sample), repr(sample)), ("Sample", "Sample", "Sample()"))


class InitOnceTest(unittest.TestCase):
    def test_init_runs_once(self):
        runs = []
        Sample = fresh(__init__=lambda self, *a, **k: runs.append(1))
        Sample()
        Sample()
        self.assertEqual(len(runs), 1)

    def test_init_runs_once_under_threads_and_nobody_sees_a_half_built_object(self):
        runs, seen = [], []

        def init(self):
            runs.append(1)
            time.sleep(0.05)
            self.ready = True

        Sample = fresh(__init__=init)
        barrier = threading.Barrier(THREADS)

        def go():
            barrier.wait()
            obj = Sample()
            seen.append(getattr(obj, "ready", False))

        threads = [threading.Thread(target=go) for _ in range(THREADS)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)
        self.assertEqual(len(runs), 1)
        self.assertEqual(seen, [True] * THREADS)

    def test_a_chain_of_inits_each_runs_once(self):
        log = []

        def parent_init(self):
            log.append("parent")

        def child_init(self):
            super(Child, self).__init__()
            log.append("child")

        Parent = fresh(__init__=parent_init)
        Child = type("Child", (Parent,), {"__init__": child_init})
        Child()
        Child()
        self.assertEqual(log, ["parent", "child"])

    def test_a_singleton_built_inside_another_singletons_init_is_initialised_once(self):
        inner_runs = []
        Inner = fresh(__init__=lambda self: inner_runs.append(1))
        Outer = fresh(__init__=lambda self: (Inner(), Inner()))
        Outer()
        Inner()
        self.assertEqual(len(inner_runs), 1)


class FailureTest(unittest.TestCase):
    def test_a_failing_init_propagates_and_is_retried(self):
        attempts = []

        def init(self):
            attempts.append(1)
            if len(attempts) == 1:
                raise RuntimeError("config down")
            self.ready = True

        Sample = fresh(__init__=init)
        with self.assertRaises(RuntimeError):
            Sample()
        self.assertTrue(Sample().ready)
        self.assertEqual(len(attempts), 2)

    def test_a_child_failure_after_the_parent_init_is_retried_as_a_whole(self):
        log, state = [], {"fail": True}

        def parent_init(self):
            log.append("parent")

        def child_init(self):
            super(Child, self).__init__()
            if state["fail"]:
                raise RuntimeError("child down")
            log.append("child")

        Parent = fresh(__init__=parent_init)
        Child = type("Child", (Parent,), {"__init__": child_init})
        with self.assertRaises(RuntimeError):
            Child()
        state["fail"] = False
        Child()
        Child()
        self.assertEqual(log, ["parent", "parent", "child"])


class ArgumentsTest(unittest.TestCase):
    def build(self):
        return fresh(__init__=lambda self, value=None, **kw: setattr(self, "value", value))

    def test_different_arguments_on_a_later_call_are_reported(self):
        Sample = self.build()
        Sample(1)
        with self.assertWarns(RuntimeWarning):
            same = Sample(2)
        self.assertEqual(same.value, 1)

    def test_the_same_or_no_arguments_are_not_reported(self):
        Sample = self.build()
        Sample(1)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            Sample(1)
            Sample()

    def test_arguments_that_cannot_be_compared_do_not_break_the_call(self):
        class Odd:
            def __eq__(self, other):
                raise RuntimeError("no comparison")

        Sample = self.build()
        Sample(Odd())
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            Sample(Odd())


class SlotsTest(unittest.TestCase):
    def test_a_slotted_subclass_needs_no_extra_slot(self):
        class Slotted(Singleton):
            __slots__ = ("value",)

            def __init__(self):
                self.value = 1

        self.assertIs(Slotted(), Slotted())
        self.assertEqual(Slotted().value, 1)

    def test_a_subclass_that_still_lists_the_flag_keeps_working(self):
        class Listed(Singleton):
            __slots__ = ("_wf_initialized", "value")

            def __init__(self):
                self.value = 2

        self.assertEqual(Listed().value, 2)

    def test_the_flag_is_declared_by_the_base(self):
        self.assertIn("_wf_initialized", Singleton.__slots__)


if __name__ == "__main__":
    unittest.main()
