# Module Name: helper/attributes.py
# Description: This modul contains concrete attribute handling class.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence

# import inspect
from typing import final, Optional, Union

_ON = _obj_name = lambda o: o.__name__ if hasattr(o, "__name__") else None
_NC = _cls_name = lambda o: o.__class__.__name__ if hasattr(o, "__class__") else None
_NT = _typ_name = lambda o: type(o).__name__

CONVERT_TYPE_ERR = "{}: unexpected type found [{}:{}] expected [{}]"
EVAL_TYPE_ERR = "{}.{}: Unexpected type [{}], expected [{}]"


@final
class Attributes:
    __slots__ = ()

    @staticmethod
    def find_name_by_variable(obj):
        return getattr(obj, "__name__", "Unknown")

    @staticmethod
    def find_object_by_name(obj):
        return getattr(obj, "__name__", "Unknown")

    def allowed(self, allowed, **kwargs) -> bool:
        self.evaluate(allowed, list)

        if not allowed:
            return False

        restricted = set(kwargs.keys()) - set(allowed)
        if restricted:
            raise AttributeError(f"{_NC(self)} - Restricted : [{restricted}]")

        return True

    def convert(self, name: str, cls: type, **kwargs):
        if name not in kwargs:
            raise TypeError("kwargs[{name}]")

        value = kwargs[name]

        for enum_member in cls:
            if enum_member.name == value or enum_member.value == value:
                kwargs[name] = enum_member
                return

        error = CONVERT_TYPE_ERR.format(_NC(self), value, _NT(value), cls.__name__)
        raise TypeError(error)

    def evaluate(self, target, expected_type):
        if not expected_type:
            return
        if target is expected_type:
            return
        if not isinstance(target, expected_type):
            name = getattr(target, "__name__", type(target).__name__)
            expected = expected_type.__name__
            owner = getattr(self, "__name__", type(self).__name__)
            raise TypeError(
                EVAL_TYPE_ERR.format(
                    owner, self.find_name_by_variable(target), name, expected
                )
            )

    def exists(self, name: str, cls: type):
        attr = getattr(self, name, None)
        if not attr:
            raise TypeError(name)
        self.evaluate(attr, cls)

    def load_from_class(self, name: str, obj: object, cls: type, **kwargs):
        if not isinstance(obj, str):
            raise TypeError(
                f"Expected class path as string for {name}, got {type(obj).__name__}"
            )
        try:
            from wattleflow.helpers import ClassLoader

            instance = ClassLoader(obj, **kwargs).instance
        except ModuleNotFoundError:
            raise ModuleNotFoundError(f"Class {obj} not found in module.")
        except Exception as e:
            raise ValueError(f"Failed to instantiate {obj}: {e}")
        if not isinstance(instance, cls):
            raise TypeError(
                f"Loaded instance of {obj} is not a subclass of {cls.__name__}"
            )
        return instance

    def get_name(self):
        return self.__class__.__name__

    def mandatory(self, name: str, cls: type, **kwargs):
        self.evaluate(kwargs, dict)
        if name not in kwargs:
            raise TypeError(f"kwargs[{name}]")

        obj = kwargs.pop(name)

        if isinstance(obj, cls):
            self.push(name, obj)
            return obj

        if cls in [int, dict, str, tuple, list]:
            raise TypeError(f"kwargs[{name}] expected {cls.__name__}")

        return self.load_from_class(name, obj, cls, **kwargs)

    def get(self, name: str, kwargs: dict, cls: Optional[type], mandatory=True):
        if mandatory:
            if not kwargs or name not in kwargs:
                raise TypeError(self, f"kwargs[{name}]")
        item = kwargs.pop(name, None)
        if isinstance(item, cls):
            return item

        if mandatory and isinstance(item, str):
            from wattleflow.helpers import ClassLoader

            instance = ClassLoader(item, **kwargs).instance
            self.push(name, instance)
            return instance

        raise TypeError(self, name)

    def optional(self, name: str, cls: type, default: Union[object], **kwargs):
        if not kwargs and not default:
            return
        if name not in kwargs and not default:
            return
        obj = kwargs.pop(name, default)
        if not isinstance(obj, cls):
            obj = self.load_from_class(name, obj, cls, **kwargs)
        self.evaluate(obj, cls)
        self.push(name, obj)

    def push(self, name: str, value: object):
        setattr(self, name, value)

    def __str__(self):
        return (
            "\n".join(f"{k}:{v}" for k, v in self.__dict__.items())
            if hasattr(self, "__dict__")
            else ""
        )
