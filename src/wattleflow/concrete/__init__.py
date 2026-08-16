# Module name: concrete/__init__.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

# Eager aggregate (CLAUDE.md §2.7 form (a)): every module here resolves inside
# the clean core tier, so importing a name pulls in nothing third-party.
# This entry point serves consumers outside the distribution; framework code
# imports the submodule directly, because importing through the package would
# make the internal dependency graph cyclic.

from . import (
    base,
    blackboard,
    connection,
    document,
    driver,
    exception,
    helpers,
    iterator,
    manager,
    memento,
    observable,
    orchestrator,
    pipeline,
    processor,
    repository,
    scheduler,
    serialisation,
    singleton,
    state_machine,
    strategy,
    workflow,
)
from .base import *  # noqa: F403
from .blackboard import *  # noqa: F403
from .connection import *  # noqa: F403
from .document import *  # noqa: F403
from .driver import *  # noqa: F403
from .exception import *  # noqa: F403
from .helpers import *  # noqa: F403
from .iterator import *  # noqa: F403
from .manager import *  # noqa: F403
from .memento import *  # noqa: F403
from .observable import *  # noqa: F403
from .orchestrator import *  # noqa: F403
from .pipeline import *  # noqa: F403
from .processor import *  # noqa: F403
from .repository import *  # noqa: F403
from .scheduler import *  # noqa: F403
from .serialisation import *  # noqa: F403
from .singleton import *  # noqa: F403
from .state_machine import *  # noqa: F403
from .strategy import *  # noqa: F403
from .workflow import *  # noqa: F403

__all__ = [
    *base.__all__,
    *blackboard.__all__,
    *connection.__all__,
    *document.__all__,
    *driver.__all__,
    *exception.__all__,
    *helpers.__all__,
    *iterator.__all__,
    *manager.__all__,
    *memento.__all__,
    *observable.__all__,
    *orchestrator.__all__,
    *pipeline.__all__,
    *processor.__all__,
    *repository.__all__,
    *scheduler.__all__,
    *serialisation.__all__,
    *singleton.__all__,
    *state_machine.__all__,
    *strategy.__all__,
    *workflow.__all__,
]
