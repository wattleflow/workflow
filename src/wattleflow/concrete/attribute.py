# Module Name: core/helpers/attribute.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains attribute handling class.

import os
import inspect
from typing import Optional, Union
from importlib import import_module
from wattleflow.core import IStrategy

CLASSLOADER_LEVELUP = 2

SPECIAL_TYPES = [
    "ABCMeta",
    "function",
    "_Generic",
    None,
    "None",
    "NoneType",
    "type",
    "<lambda>",
]

_ON = _obj_name = lambda o: o.__name__ if hasattr(o, "__name__") else None
_NC = _cls_name = lambda o: o.__class__.__name__ if hasattr(o, "__class__") else None
_NT = _typ_name = lambda o: type(o).__name__


class MissingAttribute(TypeError):
    def __init__(self, caller, error, **kwargs):
        msg = f"{_NC(caller)}.{error}"
        if kwargs:
            msg += f" {kwargs}"
        super().__init__(f"Missing: [{msg}].")


class StrategyClassLoader(IStrategy):
    def execute(self, class_path, root_path):
        class_path, class_name = class_path.rsplit(".", 1)
        module_path = class_path.replace(".", os.path.sep)
        module_path = os.path.join(root_path, "{}.py".format(module_path))

        if not os.path.exists(module_path):
            raise ModuleNotFoundError(module_path)

        module = import_module(class_path)

        if class_name in module.__dict__:
            return module.__dict__[class_name]

        raise ModuleNotFoundError(class_path)


class ClassLoader:
    def __init__(self, class_path, **kwargs):
        self.loader_strategy = StrategyClassLoader()
        path_parts = os.path.dirname(os.path.abspath(__file__)).split(os.path.sep)
        root_path = os.path.sep.join(
            path_parts[:-CLASSLOADER_LEVELUP]
            if len(path_parts) > CLASSLOADER_LEVELUP
            else path_parts
        )
        self.cls = self.loader_strategy.execute(
            class_path=class_path, root_path=root_path
        )
        self.instance = self.cls(**kwargs)


class Attribute:
    @staticmethod
    def find_name_by_variable(obj):
        depth = 0
        frame = inspect.currentframe()
        while frame and depth < 5:
            for key, value in frame.f_back.f_locals.items():
                # print(f"Frame {depth}: {key}:{value} [{frame.f_code.co_name}]")
                if value is obj:
                    return value
            frame = frame.f_back
            depth += 1
        return None

    @staticmethod
    def find_object_by_name(name):
        locals = inspect.currentframe().f_back.f_locals
        if name in locals:
            return locals[name]
        return None

    def evaluate(self, target, expected_type):
        if not expected_type:
            return

        if target is expected_type:
            return

        varname = self.find_name_by_variable(target)
        name = target.__name__ if hasattr(target, "__name__") else type(target).__name__
        expected = expected_type.__name__
        owner = self.__name__ if hasattr(self, "__name__") else type(self).__name__
        error = (
            f"{owner}.{varname}: Unexpected type found [{name}] expected [{expected}]"
        )

        if not isinstance(target, expected_type):
            raise TypeError(error)

    def load_from_class(self, name: str, obj: object, cls: type, **kwargs):
        if not isinstance(obj, str):
            raise ReferenceError(f"Not a class value. [{name}]")

        instance = ClassLoader(obj, **kwargs).instance

        if not isinstance(instance, cls):
            raise ReferenceError("Incorrect type.")

        return instance

    def get_name(self):
        return self.__class__.__name__

    def allowed(self, allowed, **kwargs) -> bool:
        self.evaluate(allowed, list)

        if not len(allowed) > 0:
            return False

        restricted = set(kwargs.keys()) - set(allowed)

        if restricted:
            raise AttributeError(f"Restricted: {_NC(self)}.allowed[{restricted}]")

        return True

    def exists(self, name: str, cls: type):
        attr = getattr(self, name, None)
        if not attr:
            raise MissingAttribute(self, name)

        self.evaluate(attr, cls)

    def get(self, name: str, kwargs: dict, cls: Optional[type], mandatory=True):
        if mandatory:
            if not kwargs:
                raise MissingAttribute(self, "kwargs")

            if name not in kwargs:
                raise MissingAttribute(self, f"kwargs[{name}]")

        item = kwargs.pop(name, None)

        if isinstance(item, cls):
            return item

        try:
            if mandatory:
                if isinstance(item, str):
                    instance = ClassLoader(item, **kwargs).instance
                    self.push(name, instance)
                else:
                    raise MissingAttribute(self, name)
        except Exception as e:
            raise MissingAttribute(self, name, e)

    def push(self, name: str, value: object):
        setattr(self, name, value)

    def convert(self, name: str, cls: type, **kwargs):
        if name not in kwargs:
            raise MissingAttribute(self, f"kwargs[{name}]")

        value = kwargs[name]

        for enum_member in cls:
            if enum_member.name == value or enum_member.value == value:
                kwargs[name] = enum_member
                return

        txt = "{}: unexpected type found [{}:{}] expected [{}]"
        error = txt.format(_NC(self), value, _NT(value), cls.__class__.__name__)
        raise TypeError(error)

    def mandatory(self, name: str, cls: type, **kwargs):
        self.evaluate(kwargs, dict)

        if name not in kwargs:
            raise MissingAttribute(self, f"kwargs[{name}]")

        obj = kwargs.pop(name, None)

        if isinstance(obj, cls):
            self.push(name, obj)
            return obj

        if cls in [int, dict, str, tuple, list]:
            raise TypeError(f"kwargs[{name}]")

        try:
            self.load_from_class(name, obj, cls, **kwargs)
        except Exception as e:
            raise ValueError(f"Error loading class: kwargs[{name}]: {e}")

    def optional(self, name: str, cls: type, default: Union[object], **kwargs):
        if (not kwargs) and (not default):
            return

        if (name not in kwargs) and (not default):
            return

        obj = kwargs.pop(name, default)

        if not isinstance(obj, cls):
            obj = self.load_from_class(name, obj, cls, **kwargs)

        if default:
            self.evaluate(obj, cls)

        self.push(name, obj)

    def __str__(self):
        attributes = ""
        for k, v in self.__dict__.items():
            attributes += f"{k}:{v}\n"
        return attributes
