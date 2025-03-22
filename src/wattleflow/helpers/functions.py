# Module Name: helpers/functions.py
# Description: This modul contains helper methods.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence

import re

list_all = lambda o: [print(f"{k}: {v}") for k, v in o.__dict__.items()]
list_vars = lambda o: [
    n for n in vars(o) if not n.startswith("_") or not n.endswith("_")
]
list_dir = lambda o: [
    n for n in dir(o) if not n.startswith("_") and not n.endswith("_")
]
list_properties = lambda o: [
    print(f"{k}: {v}")
    for k, v in o.__dict__.items()
    if not k.startswith("_") and not k.endswith("_")
]

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

_obj_name = lambda o: o.__name__ if hasattr(o, "__name__") else None
_cls_name = lambda o: o.__class__.__name__ if hasattr(o, "__class__") else None
_typ_name = lambda o: type(o).__name__

_ON = _obj_name
_NC = _cls_name
_NT = _typ_name


def sql_name(sql):
    """Generates a concise name for the given SQL query."""
    # Extract the operation (e.g., SELECT, INSERT) and the target table/schema
    mask = r"^(SELECT|INSERT|UPDATE|DELETE)\s+.*?\s+(FROM|INTO|UPDATE|DELETE)?\s+([a-zA-Z0-9_.]+)"
    match = re.search(mask, sql, re.IGNORECASE)
    if match:
        operation = match.group(1).strip().lower()
        target = match.group(3).strip().lower()
        return f"{operation}_{target}"
    else:
        return "unrecognisable_sql_name"
