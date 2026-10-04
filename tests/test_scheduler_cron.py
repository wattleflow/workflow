# Module name: tests/test_scheduler_cron.py
# SchedulerCronJob (the consumer of Scheduler, FRQ-SCH): a failed pass never stops the loop, not even
# when a listener of its error event fails.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_scheduler_cron -v
import logging
import unittest
from unittest.mock import MagicMock, patch

from wattleflow.core import IConfig
from wattleflow.enums.event import Event
from wattleflow.schedulers import SchedulerCronJob
from tests.test_scheduler import BrokenListener, Listener


def cron(**kwargs):
    adapter = MagicMock(spec=IConfig)
    adapter.find.return_value = None  # no workflow declared: every pass fails
    return SchedulerCronJob(adapter=adapter, heartbeat=0, level=logging.CRITICAL, **kwargs)


class CronJobTest(unittest.TestCase):
    def test_a_failed_pass_is_reported_to_the_listeners(self):
        job, listener = cron(), Listener()
        job.register_listener(listener)
        self.assertFalse(job.run_once())
        self.assertEqual([entry[1] for entry in listener.log], [Event.CronJobSchedulerError])
        self.assertEqual((job.passes, job.failures), (1, 1))

    def test_a_failing_listener_does_not_break_the_pass(self):
        job, listener = cron(), Listener()
        job.register_listener(BrokenListener())
        job.register_listener(listener)
        self.assertFalse(job.run_once())
        self.assertEqual(len(listener.log), 1)

    def test_the_loop_survives_failing_passes_and_failing_listeners(self):
        job = cron()
        job.register_listener(BrokenListener())
        with patch("wattleflow.schedulers.cron_job.time.sleep") as sleep:
            job.run(cycles=3)
        self.assertEqual((job.passes, job.failures), (3, 3))
        self.assertEqual(sleep.call_count, 2)


if __name__ == "__main__":
    unittest.main()
