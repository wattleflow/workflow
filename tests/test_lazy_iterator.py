# Module name: tests/test_lazy_iterator.py
# Tests for LazyIterator and LazyAsyncIterator (FRQ-ITR, DEF-ITR-01): the source is built on the first
# fetch and kept; an instance is a single-pass iterator (iter(x) is x), and a new pass comes from the
# aggregate that creates a new iterator (ISyncAggregate), as Catalog does.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_lazy_iterator -v
import asyncio
import itertools
import unittest

from wattleflow.concrete.iterator import LazyAsyncIterator, LazyIterator


class Source(LazyIterator):
    built = 0

    def create_iterator(self):
        type(self).built += 1
        return iter([1, 2, 3, 4, 5, 6])


class Flaky(LazyIterator):
    attempts = 0

    def create_iterator(self):
        type(self).attempts += 1
        if type(self).attempts == 1:
            raise RuntimeError("source down")
        return iter([1, 2])


class Aggregate:
    def create_iterator(self):
        return Source()


class AsyncSource(LazyAsyncIterator):
    built = 0

    def create_iterator(self):
        type(self).built += 1

        async def items():
            for value in (1, 2, 3):
                yield value

        return items()


class AsyncFlaky(LazyAsyncIterator):
    attempts = 0

    def create_iterator(self):
        type(self).attempts += 1
        if type(self).attempts == 1:
            raise RuntimeError("source down")

        async def items():
            yield 1

        return items()


class LazyConstructionTest(unittest.TestCase):
    def setUp(self):
        Source.built = 0

    def test_nothing_is_built_at_construction(self):
        Source()
        self.assertEqual(Source.built, 0)

    def test_the_source_is_built_on_the_first_fetch(self):
        iterator = Source()
        next(iterator)
        self.assertEqual(Source.built, 1)

    def test_the_source_is_built_once_for_a_whole_pass(self):
        iterator = Source()
        self.assertEqual(list(iterator), [1, 2, 3, 4, 5, 6])
        self.assertEqual(Source.built, 1)


class SinglePassTest(unittest.TestCase):
    def test_iter_returns_the_instance_itself(self):
        iterator = Source()
        self.assertIs(iter(iterator), iterator)

    def test_an_exhausted_iterator_stays_exhausted(self):
        iterator = Source()
        list(iterator)
        self.assertEqual(list(iterator), [])
        with self.assertRaises(StopIteration):
            next(iterator)

    def test_a_partial_pass_continues_where_it_stopped(self):
        iterator = Source()
        for value in iterator:
            if value == 2:
                break
        self.assertEqual(list(iterator), [3, 4, 5, 6])

    def test_peeking_with_next_iter_advances(self):
        iterator = Source()
        self.assertEqual([next(iter(iterator)) for _ in range(3)], [1, 2, 3])

    def test_the_same_iterator_on_both_sides_of_zip_pairs_neighbours(self):
        iterator = Source()
        self.assertEqual(list(zip(iterator, iterator, strict=True)), [(1, 2), (3, 4), (5, 6)])

    def test_islice_twice_takes_consecutive_items(self):
        iterator = Source()
        self.assertEqual(
            [list(itertools.islice(iterator, 2)), list(itertools.islice(iterator, 2))],
            [[1, 2], [3, 4]],
        )

    def test_the_end_of_the_source_is_not_changed(self):
        iterator = Source()
        list(iterator)
        self.assertRaises(StopIteration, next, iterator)


class AggregatePassTest(unittest.TestCase):
    def setUp(self):
        Source.built = 0

    def test_each_call_to_the_aggregate_gives_a_new_iterator(self):
        aggregate = Aggregate()
        self.assertIsNot(aggregate.create_iterator(), aggregate.create_iterator())

    def test_a_second_pass_comes_from_a_second_iterator(self):
        aggregate = Aggregate()
        first = list(aggregate.create_iterator())
        second = list(aggregate.create_iterator())
        self.assertEqual(first, second)
        self.assertEqual(second, [1, 2, 3, 4, 5, 6])
        self.assertEqual(Source.built, 2)


class FailureTest(unittest.TestCase):
    def setUp(self):
        Flaky.attempts = 0

    def test_a_failed_build_propagates(self):
        with self.assertRaises(RuntimeError):
            next(Flaky())

    def test_a_failed_build_is_retried_on_the_next_fetch(self):
        iterator = Flaky()
        with self.assertRaises(RuntimeError):
            next(iterator)
        self.assertEqual(next(iterator), 1)
        self.assertEqual(Flaky.attempts, 2)


class SlotsTest(unittest.TestCase):
    def test_both_classes_declare_the_single_slot(self):
        self.assertEqual(LazyIterator.__slots__, ("_iterator",))
        self.assertEqual(LazyAsyncIterator.__slots__, ("_iterator",))

    def test_the_iterator_member_is_none_until_the_first_fetch(self):
        iterator = Source()
        self.assertIsNone(iterator._iterator)
        next(iterator)
        self.assertIsNotNone(iterator._iterator)


class AsyncLazyIteratorTest(unittest.TestCase):
    def setUp(self):
        AsyncSource.built = 0
        AsyncFlaky.attempts = 0

    def test_nothing_is_built_at_construction(self):
        AsyncSource()
        self.assertEqual(AsyncSource.built, 0)

    def test_one_pass_builds_once_and_the_second_pass_is_empty(self):
        async def run():
            iterator = AsyncSource()
            first = [value async for value in iterator]
            second = [value async for value in iterator]
            return first, second

        first, second = asyncio.run(run())
        self.assertEqual((first, second), ([1, 2, 3], []))
        self.assertEqual(AsyncSource.built, 1)

    def test_aiter_returns_the_instance_itself(self):
        iterator = AsyncSource()
        self.assertIs(iterator.__aiter__(), iterator)

    def test_the_end_of_the_source_is_not_changed(self):
        async def run():
            iterator = AsyncSource()
            async for _ in iterator:
                pass
            return await iterator.__anext__()

        with self.assertRaises(StopAsyncIteration):
            asyncio.run(run())

    def test_a_failed_build_is_retried_on_the_next_fetch(self):
        async def run():
            iterator = AsyncFlaky()
            try:
                await iterator.__anext__()
            except RuntimeError:
                pass
            return await iterator.__anext__()

        self.assertEqual(asyncio.run(run()), 1)
        self.assertEqual(AsyncFlaky.attempts, 2)


if __name__ == "__main__":
    unittest.main()
