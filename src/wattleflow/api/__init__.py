# Module name: __init__.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

# --------------------------------------------------------------------------- #
# You need FastApi to run this code:
#
#     pip install fastapi
#
# --------------------------------------------------------------------------- #

"""
MVC pattern interfaces for the WattleFlow framework.

Hierarchy
---------
    IWattleflow
    ├── IModel[T]        — read-only view of domain data
    ├── IView[T]         — renders a model into a response
    ├── IController[T]   — orchestrates model + view, handles a request
    └── IService[T]      — lifecycle wrapper: start / stop + controller access

Design notes
------------
- All interfaces inherit IWattleflow so they carry `.name`, `__repr__`, and
  the standard ABC contract used throughout the framework.
- Generics use the same TypeVar `T` already defined in framework.py.
- IService intentionally does NOT inherit IController; it *owns* one.
  This keeps the single-responsibility boundary clean:
    Controller  → "what to do with a request"
    Service     → "how to run and expose a controller"
- IView returns `Any` so concrete implementations can return FastAPI
  Response objects, dicts, strings, or any other transport-layer type
  without coupling the interface to a specific web framework.
"""

from __future__ import annotations
from abc import abstractmethod, ABC
from typing import Any

try:
    from fastapi.responses import HTMLResponse
except Exception as e:
    raise ModuleNotFoundError(
        f"Error: {str(e)}\nPlease install:\n   pip install fastapi"
    ) from e

from wattleflow.core.framework import IWattleflow, T


class IEndPoint(IWattleflow, ABC):
    @property
    @abstractmethod
    def render(self, **kwargs) -> HTMLResponse: ...


class IController(IWattleflow, ABC):
    @abstractmethod
    def handle(self, request: Any, **kwargs) -> Any: ...


class IModel(IWattleflow, ABC):
    @property
    @abstractmethod
    def data(self) -> Any: ...

    @property
    @abstractmethod
    def is_ready(self) -> bool: ...


class IView(IWattleflow, ABC):
    @abstractmethod
    def render(self, model: IModel) -> HTMLResponse: ...
