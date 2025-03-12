# Module Name: name schedulers/cron_job.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains concrete cron job class.

import time
from concrete.scheduler import Scheduler


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
                self.setup_orchestrator(self.config_path)
                self.start_orchestration(
                    parallel=True
                )  # Can be changed based on config
            except Exception as e:
                self.emit_event("CronJobSchedulerError", error=str(e))
            finally:
                self.stop_orchestration()

            self.emit_event("Sleeping", duration=self.heartbeat)
            time.sleep(self.heartbeat)  # Wait until next execution
