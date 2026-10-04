# Module name: tests/test_lazy_iterator_threads.py
# Tests for ThreadSafeLazyIterator (FRQ-ITR, DEF-ITR-02): concurrent first fetches build the source once.
# LazyIterator itself stays lock-free; the race is shown on it as the reason for the thread-safe variant.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_lazy_iterator_threads -v
import threading
import time
import unittest

from wattleflow.concrete.iterator import LazyIterator, ThreadSafeLazyIterator

THREADS = 8


def slow(base):
    class Slow(base):
        built = 0

        def create_iterator(self):
            type(self).built += 1
            time.sleep(0.01)
            return iter(range(100))

    return Slow


def hammer(iterator):
    barrier = threading.Barrier(THREADS)
    fetched, errors = [], []

    def work():
        barrier.wait()
        try:
            fetched.append(next(iterator))
        except Exception as error:
            errors.append(error)

    threads = [threading.Thread(target=work) for _ in range(THREADS)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return fetched, errors


class RaceTest(unittest.TestCase):
    def test_the_plain_iterator_builds_more_than_once_under_threads(self):
        cls = slow(LazyIterator)
        hammer(cls())
        self.assertGreater(cls.built, 1)

    def test_the_thread_safe_iterator_builds_once(self):
        for _ in range(10):
            cls = slow(ThreadSafeLazyIterator)
            fetched, errors = hammer(cls())
            self.assertEqual(cls.built, 1)
            self.assertEqual(errors, [])
            self.assertEqual(sorted(fetched), list(range(THREADS)))


class ContractTest(unittest.TestCase):
    def test_it_is_a_lazy_iterator(self):
        self.assertTrue(issubclass(ThreadSafeLazyIterator, LazyIterator))

    def test_nothing_is_built_at_construction(self):
        cls = slow(ThreadSafeLazyIterator)
        cls()
        self.assertEqual(cls.built, 0)

    def test_the_lock_does_not_shadow_the_audit_lock(self):
        self.assertIn("_build_lock", ThreadSafeLazyIterator.__slots__)
        self.assertNotIn("_lock", ThreadSafeLazyIterator.__slots__)

    def test_a_failed_build_is_retried_and_the_lock_is_released(self):
        class Flaky(ThreadSafeLazyIterator):
            attempts = 0

            def create_iterator(self):
                type(self).attempts += 1
                if type(self).attempts == 1:
                    raise RuntimeError("source down")
                return iter([1])

        iterator = Flaky()
        with self.assertRaises(RuntimeError):
            next(iterator)
        self.assertEqual(next(iterator), 1)
        self.assertEqual(Flaky.attempts, 2)

    def test_the_end_of_the_source_is_not_changed(self):
        iterator = slow(ThreadSafeLazyIterator)()
        self.assertEqual(len(list(iterator)), 100)
        with self.assertRaises(StopIteration):
            next(iterator)


if __name__ == "__main__":
    unittest.main()
