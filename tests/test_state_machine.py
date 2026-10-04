# Module name: tests/test_state_machine.py
# Tests for StateMachine and GuardedStateMachine (FRQ-SMC): only the transitions in the table, a table
# the owner cannot change from outside, check-and-apply that is atomic under threads, a start state that
# belongs to the table, and a guard that runs once before the first transition.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_state_machine -v
import threading
import time
import unittest
from enum import Enum

from wattleflow.concrete.state_machine import GuardedStateMachine, StateMachine

THREADS = 8


class S(Enum):
    A = 1
    B = 2
    C = 3


class Act(Enum):
    GO = 1
    BACK = 2
    STAY = 3


TABLE = {
    (S.A, Act.GO): S.B,
    (S.B, Act.GO): S.C,
    (S.B, Act.BACK): S.A,
    (S.B, Act.STAY): S.B,
}


def machine(table=None, initial=S.A, **kwargs):
    return StateMachine(dict(TABLE) if table is None else table, initial, **kwargs)


class TransitionTest(unittest.TestCase):
    def test_apply_moves_along_the_table(self):
        m = machine()
        m.apply(Act.GO)
        self.assertIs(m.state, S.B)
        m.apply(Act.GO)
        self.assertIs(m.state, S.C)

    def test_a_transition_into_the_same_state_is_allowed_when_listed(self):
        m = machine(initial=S.B)
        m.apply(Act.STAY)
        self.assertIs(m.state, S.B)

    def test_an_action_that_is_not_listed_raises_and_keeps_the_state(self):
        m = machine()
        with self.assertRaises(ValueError) as caught:
            m.apply(Act.BACK)
        self.assertIs(m.state, S.A)
        self.assertIn("BACK", str(caught.exception))

    def test_can_answers_without_changing_the_state(self):
        m = machine()
        self.assertTrue(m.can(Act.GO))
        self.assertFalse(m.can(Act.BACK))
        self.assertIs(m.state, S.A)

    def test_try_apply_applies_when_allowed_and_answers_false_otherwise(self):
        m = machine()
        self.assertFalse(m.try_apply(Act.BACK))
        self.assertIs(m.state, S.A)
        self.assertTrue(m.try_apply(Act.GO))
        self.assertIs(m.state, S.B)

    def test_state_is_read_only(self):
        with self.assertRaises(AttributeError):
            machine().state = S.C

    def test_the_name_defaults_to_the_class_and_can_be_given(self):
        self.assertEqual(machine().name, "StateMachine")
        self.assertEqual(machine(name="ProcessorFSM").name, "ProcessorFSM")

    def test_repr_shows_name_and_state(self):
        self.assertEqual(repr(machine(name="M")), "M:[A]")


class TableTest(unittest.TestCase):
    def test_changing_the_owners_table_afterwards_does_not_change_the_machine(self):
        table = dict(TABLE)
        m = machine(table)
        table[(S.A, Act.BACK)] = S.C
        del table[(S.A, Act.GO)]
        self.assertTrue(m.can(Act.GO))
        self.assertFalse(m.can(Act.BACK))

    def test_the_machines_own_table_cannot_be_written(self):
        m = machine()
        with self.assertRaises(TypeError):
            m._transitions[(S.A, Act.BACK)] = S.C

    def test_the_start_state_must_appear_in_the_table(self):
        with self.assertRaises(ValueError):
            machine(initial="IDLE")

    def test_a_target_only_state_is_a_valid_start(self):
        machine(initial=S.C)


class ThreadsTest(unittest.TestCase):
    def test_two_threads_cannot_both_take_the_same_transition(self):
        class Slow(dict):
            def __contains__(self, key):
                found = super().__contains__(key)
                time.sleep(0.02)  # widen the window between the check and the write
                return found

        m = machine({(S.A, Act.GO): S.B})
        m._transitions = Slow(m._transitions)
        outcome, barrier = [], threading.Barrier(THREADS)

        def go():
            barrier.wait()
            try:
                m.apply(Act.GO)
                outcome.append("ok")
            except ValueError:
                outcome.append("refused")

        threads = [threading.Thread(target=go) for _ in range(THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(10)
        self.assertEqual(outcome.count("ok"), 1)
        self.assertEqual(outcome.count("refused"), THREADS - 1)

    def test_try_apply_is_atomic_too(self):
        m = machine({(S.A, Act.GO): S.B})
        results, barrier = [], threading.Barrier(THREADS)

        def go():
            barrier.wait()
            results.append(m.try_apply(Act.GO))

        threads = [threading.Thread(target=go) for _ in range(THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(10)
        self.assertEqual(results.count(True), 1)


class GuardTest(unittest.TestCase):
    def test_the_guard_runs_before_the_first_transition_and_only_once(self):
        calls = []
        g = GuardedStateMachine(machine(), lambda inner: calls.append(inner.state))
        g.apply(Act.GO)
        g.apply(Act.GO)
        self.assertEqual(calls, [S.A])
        self.assertIs(g.state, S.C)

    def test_a_failing_guard_blocks_the_transition_and_is_retried(self):
        attempts = []

        def guard(inner):
            attempts.append(1)
            if len(attempts) == 1:
                raise PermissionError("not yet")

        g = GuardedStateMachine(machine(), guard)
        with self.assertRaises(PermissionError):
            g.apply(Act.GO)
        self.assertIs(g.state, S.A)
        g.apply(Act.GO)
        self.assertEqual(len(attempts), 2)
        self.assertIs(g.state, S.B)

    def test_the_guard_runs_once_under_threads(self):
        calls, barrier = [], threading.Barrier(THREADS)

        def guard(inner):
            calls.append(1)
            time.sleep(0.03)

        g = GuardedStateMachine(machine({(S.A, Act.GO): S.A}), guard)

        def go():
            barrier.wait()
            g.apply(Act.GO)

        threads = [threading.Thread(target=go) for _ in range(THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(10)
        self.assertEqual(len(calls), 1)

    def test_can_state_inner_and_name_pass_through(self):
        inner = machine(name="M")
        g = GuardedStateMachine(inner, lambda i: None)
        self.assertTrue(g.can(Act.GO))
        self.assertIs(g.state, S.A)
        self.assertIs(g.inner, inner)
        self.assertEqual(g.name, "M")

    def test_a_given_name_wins_over_the_inner_name(self):
        self.assertEqual(GuardedStateMachine(machine(name="M"), lambda i: None, name="G").name, "G")

    def test_both_classes_are_generic(self):
        self.assertIsNotNone(StateMachine[S, Act])
        self.assertIsNotNone(GuardedStateMachine[S, Act])

    def test_both_classes_declare_their_slots(self):
        self.assertIn("_transitions", StateMachine.__slots__)
        self.assertIn("_consumed", GuardedStateMachine.__slots__)


if __name__ == "__main__":
    unittest.main()
