# Module name: tests/test_observable.py
# Tests for ThreadSafeObservable (FRQ-OBS): the observer list, delivery outside the lock over a snapshot,
# observer failures logged without stopping the others, and construction (the lock slot must not shadow
# Audit._lock, which Audit.__init__ takes before the subclass could assign its own).
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_observable -v
import logging
import threading
import unittest

from wattleflow.concrete.exception import AttributeException
from wattleflow.concrete.observable import ThreadSafeObservable
from wattleflow.core.concurrent import IObserverReactive
from wattleflow.helpers.audit import Audit


class Recorder(IObserverReactive):
    def __init__(self, label="r", log=None):
        self.label = label
        self.log = log if log is not None else []

    @property
    def name(self):
        return self.label

    def update(self, observable, *args, **kwargs):
        self.log.append((self.label, observable, args, kwargs))


class Broken(IObserverReactive):
    @property
    def name(self):
        return "broken"

    def update(self, observable, *args, **kwargs):
        raise RuntimeError("observer down")


class ConstructionTest(unittest.TestCase):
    def test_the_observable_can_be_constructed(self):
        ThreadSafeObservable()

    def test_the_lock_slot_does_not_shadow_the_audit_lock(self):
        self.assertNotIn("_lock", ThreadSafeObservable.__slots__)
        self.assertIs(ThreadSafeObservable._lock, Audit._lock)

    def test_the_slots_are_the_declared_ones(self):
        self.assertEqual(ThreadSafeObservable.__slots__, ("_observers", "_observers_lock"))

    def test_two_instances_do_not_share_observers(self):
        first, second = ThreadSafeObservable(), ThreadSafeObservable()
        first.add_observer(Recorder())
        second.notify_observers("x")
        self.assertEqual(second._observers, [])


class ListTest(unittest.TestCase):
    def setUp(self):
        self.subject = ThreadSafeObservable()

    def test_an_observer_is_added_once(self):
        observer = Recorder()
        self.subject.add_observer(observer)
        self.subject.add_observer(observer)
        self.assertEqual(self.subject._observers, [observer])

    def test_observers_are_kept_in_the_order_of_subscription(self):
        log = []
        for name in "abc":
            self.subject.add_observer(Recorder(name, log))
        self.subject.notify_observers()
        self.assertEqual([entry[0] for entry in log], ["a", "b", "c"])

    def test_removing_an_unknown_observer_is_silent(self):
        self.subject.remove_observer(Recorder())

    def test_a_removed_observer_is_not_notified(self):
        log = []
        keep, drop = Recorder("keep", log), Recorder("drop", log)
        self.subject.add_observer(keep)
        self.subject.add_observer(drop)
        self.subject.remove_observer(drop)
        self.subject.notify_observers()
        self.assertEqual([entry[0] for entry in log], ["keep"])

    def test_notifying_an_empty_observable_is_a_no_op(self):
        self.subject.notify_observers("x")


class Equal(Recorder):
    """Observers a value comparison cannot tell apart."""

    def __eq__(self, other):
        return isinstance(other, Equal)

    __hash__ = None


class IdentityTest(unittest.TestCase):
    def test_two_equal_but_distinct_observers_are_both_subscribed(self):
        subject, log = ThreadSafeObservable(), []
        subject.add_observer(Equal("a", log))
        subject.add_observer(Equal("b", log))
        subject.notify_observers()
        self.assertEqual([entry[0] for entry in log], ["a", "b"])

    def test_removing_removes_that_observer_and_not_an_equal_one(self):
        subject, log = ThreadSafeObservable(), []
        first, second = Equal("a", log), Equal("b", log)
        subject.add_observer(first)
        subject.add_observer(second)
        subject.remove_observer(second)
        subject.notify_observers()
        self.assertEqual([entry[0] for entry in log], ["a"])

    def test_an_equal_but_unsubscribed_observer_is_not_removed_by_value(self):
        subject, log = ThreadSafeObservable(), []
        subject.add_observer(Equal("a", log))
        subject.remove_observer(Equal("stranger", log))
        subject.notify_observers()
        self.assertEqual([entry[0] for entry in log], ["a"])

    def test_the_same_object_is_still_added_once(self):
        subject, observer = ThreadSafeObservable(), Equal()
        subject.add_observer(observer)
        subject.add_observer(observer)
        self.assertEqual(len(subject._observers), 1)


class TypeCheckTest(unittest.TestCase):
    def test_an_object_that_is_not_an_observer_is_rejected_at_add(self):
        subject = ThreadSafeObservable()
        for candidate in (object(), None, "update", lambda *a, **k: None):
            with self.subTest(candidate=candidate), self.assertRaises(AttributeException):
                subject.add_observer(candidate)
        self.assertEqual(subject._observers, [])


class DeliveryTest(unittest.TestCase):
    def setUp(self):
        self.subject = ThreadSafeObservable()

    def test_update_receives_the_source_and_the_event(self):
        recorder = Recorder()
        self.subject.add_observer(recorder)
        self.subject.notify_observers("event", 3, key="v")
        self.assertEqual(recorder.log, [("r", self.subject, ("event", 3), {"key": "v"})])

    def test_a_failing_observer_does_not_stop_the_others(self):
        log = []
        self.subject.add_observer(Recorder("a", log))
        self.subject.add_observer(Broken())
        self.subject.add_observer(Recorder("c", log))
        with self.assertLogs(level=logging.ERROR):
            self.subject.notify_observers()
        self.assertEqual([entry[0] for entry in log], ["a", "c"])

    def test_the_failure_is_logged_with_the_event_the_reason_and_the_error(self):
        self.subject.add_observer(Broken())
        with self.assertLogs(level=logging.ERROR) as logged:
            self.subject.notify_observers()
        text = "\n".join(logged.output)
        for part in ("Notify", "Observer raised during update", "observer down"):
            self.assertIn(part, text)

    def test_the_failure_is_not_raised_to_the_caller(self):
        self.subject.add_observer(Broken())
        with self.assertLogs(level=logging.ERROR):
            self.assertIsNone(self.subject.notify_observers())

    def test_an_observer_that_unsubscribes_itself_does_not_disturb_the_pass(self):
        log = []
        subject = self.subject

        class Once(Recorder):
            def update(self, observable, *args, **kwargs):
                super().update(observable, *args, **kwargs)
                subject.remove_observer(self)

        subject.add_observer(Once("once", log))
        subject.add_observer(Recorder("after", log))
        subject.notify_observers()
        subject.notify_observers()
        self.assertEqual([entry[0] for entry in log], ["once", "after", "after"])

    def test_an_observer_added_during_a_pass_hears_only_the_next_one(self):
        log = []
        subject = self.subject
        late = Recorder("late", log)

        class Adder(Recorder):
            def update(self, observable, *args, **kwargs):
                super().update(observable, *args, **kwargs)
                subject.add_observer(late)

        subject.add_observer(Adder("adder", log))
        subject.notify_observers()
        subject.notify_observers()
        self.assertEqual([entry[0] for entry in log], ["adder", "adder", "late"])

    def test_delivery_happens_outside_the_lock(self):
        subject = self.subject
        done = threading.Event()

        class Other(Recorder):
            def update(self, observable, *args, **kwargs):
                worker = threading.Thread(target=lambda: (subject.add_observer(Recorder("x")), done.set()))
                worker.start()
                worker.join(timeout=2)

        subject.add_observer(Other())
        subject.notify_observers()
        self.assertTrue(done.is_set(), "another thread could not subscribe during a pass")


class ThreadsTest(unittest.TestCase):
    def test_concurrent_subscription_removal_and_delivery_stay_consistent(self):
        subject = ThreadSafeObservable()
        stable = Recorder("stable")
        subject.add_observer(stable)
        errors = []
        barrier = threading.Barrier(9)

        def churn(index):
            barrier.wait()
            try:
                for _ in range(200):
                    observer = Recorder(f"t{index}")
                    subject.add_observer(observer)
                    subject.remove_observer(observer)
            except Exception as error:  # pragma: no cover
                errors.append(error)

        def notify():
            barrier.wait()
            try:
                for _ in range(200):
                    subject.notify_observers("e")
            except Exception as error:  # pragma: no cover
                errors.append(error)

        threads = [threading.Thread(target=churn, args=(i,)) for i in range(8)]
        threads.append(threading.Thread(target=notify))
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)
        self.assertEqual(errors, [])
        self.assertEqual(subject._observers, [stable])
        self.assertEqual(len(stable.log), 200)


if __name__ == "__main__":
    unittest.main()
