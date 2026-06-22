# Module name: helpers/audit.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


import logging
# import asyncio
# from logging.handlers import QueueHandler


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


# def setup_logging():
#     queue = asyncio.Queue()
#     logger = logging.getLogger("GlobalLogger")
#     logger.setLevel(logging.DEBUG)

#     audit_handler = AsyncAuditHandler(queue)
#     formatter = logging.Formatter(
#         "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
#     )
#     audit_handler.setFormatter(formatter)
#     logger.addHandler(audit_handler)
#     return logger, queue
