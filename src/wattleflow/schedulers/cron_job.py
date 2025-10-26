# Module name: cron_job.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Description: This module initialises the scheduler package by exposing the CronJobScheduler
class, which manages and executes scheduled tasks within the Wattleflow framework.
"""

from __future__ import annotations
import time
from concrete.scheduler import Scheduler
from constants.enums import Event


class CronJobScheduler(Scheduler):
    def __init__(self, config_path: str, heartbeat: int = 300):
        """
        :param config_path: Path to configuration file (YAML/JSON)
        :param heartbeat: Execution interval in seconds (default: 300s = 5 minutes)
        """
        super().__init__()
        self.config_path = config_path
        self.heartbeat = heartbeat

    def run(self):
        while True:
            try:
                self.setup_orchestrator()
                self.start_orchestration(parallel=True)
            except Exception as e:
                self.emit_event(event=Event.CronJobSchedulerError, error=str(e))
            finally:
                self.stop_orchestration()

            self.emit_event(event=Event.Sleeping, duration=self.heartbeat)
            time.sleep(self.heartbeat)  # Wait until next execution
