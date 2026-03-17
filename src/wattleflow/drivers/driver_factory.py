# Module name: driver_factory.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence

import logging
from abc import ABC
from typing import Optional
from wattleflow.core.creational import IFactory
from wattleflow.constants import Event
from wattleflow.concrete import AuditException, AuditLogger, GenericDriverClass


# region DriverFactory
class DriverFactory(IFactory, AuditLogger, ABC):
    def __init__(
        self,
        level: int,
        handler: Optional[logging.Handler] = None,
        *args,
        **kwargs,
    ):
        IFactory.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler, *args, **kwargs)
        self.debug(
            msg=Event.Constructor.value,
            status=Event.Completed.value,
        )

    @staticmethod
    def create(
        local_path: str,
        is_remote: bool,
        normalised: bool,
        level: int,
        handler: Optional[logging.Handler] = None,
        **kwargs,
    ) -> GenericDriverClass:
        try:
            if is_remote:
                from wattleflow.drivers.http_file_system_driver import (
                    HttpFileSystemDriver,
                )

                return HttpFileSystemDriver(
                    level=level,
                    handler=handler,
                    local_path=local_path,
                    create=True,
                    normalised=normalised,
                    **kwargs,
                )
            else:
                from wattleflow.drivers.local_file_system_driver import (
                    LocalFileSystemDriver,
                )

                return LocalFileSystemDriver(
                    local_path=local_path,
                    level=level,
                    handler=handler,
                    create=False,
                    normalised=normalised,
                )
        except AuditException as e:
            raise RuntimeError(f"DriverFactory.local_driver: {e.reason}") from e
        except Exception as e:
            raise RuntimeError(f"DriverFactory.local_driver: {e}") from e


# endregion DriverFactory
