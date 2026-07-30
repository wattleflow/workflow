# Module name: helpers/audit.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


import logging


class AsyncAuditHandler(logging.Handler):
    def __init__(self, queue):
        super().__init__()
        self.queue = queue

    def emit(self, record):
        try:
            log_entry = self.format(record)
            self.queue.put_nowait(log_entry)
        except Exception:
            self.handleError(record)

