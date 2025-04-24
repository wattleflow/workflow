# Module Name: name helpers/macros.py
# Description: This modul contains concrete macro classes.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence

import re

ADD_VALUE_ERROR = (
    "Tuple macro must be: (pattern, replacement) or (pattern, replacement, flags)."
)


class TextMacros:
    """
    Usage example:
        import yaml

        yaml_data = \"""
        macros:
            - pattern: '\\\\S+@\\\\S+'
            replacement: ''
        \"""

        macros_data = yaml.safe_load(yaml_data)['macros']
        self.text_macros = TextMacros(macros_data)

        # Create instance
        text_macros = TextMacros(macros_data)

        # Apply macro to text
        text = "My email is example@example.com"
        modified_text = text_macros.run(text)

        print(modified_text)  # Expected output: "My email is "
    """

    def __init__(self, list_of_macros: list = []):
        self._macros = []
        if list_of_macros is not None:
            if not isinstance(list_of_macros, list):
                raise TypeError(f"Expected list, found {type(list_of_macros).__name__}")
            self.add(list_of_macros)

    def add(self, list_of_macros: list):
        for macro in list_of_macros:
            if isinstance(macro, tuple):
                if len(macro) == 2:
                    pattern, replacement = macro
                    pattern = re.compile(pattern)
                elif len(macro) == 3:
                    pattern, replacement, flags = macro
                    pattern = re.compile(pattern, flags)
                else:
                    raise ValueError(ADD_VALUE_ERROR)
            elif isinstance(macro, dict):
                if "pattern" in macro and "replacement" in macro:
                    pattern = macro["pattern"]
                    replacement = macro["replacement"]
                    flags = macro.get("flags", 0)
                    pattern = re.compile(pattern, flags)
                else:
                    raise ValueError(
                        "Dict macro must contain 'pattern' and 'replacement'."
                    )
            else:
                raise ValueError("Macro must be either a tuple or a dict.")
            self._macros.append((pattern, replacement))

    def run(self, text):
        for pattern, replacement in self._macros:
            try:
                text = pattern.sub(replacement, text)
            except Exception:
                continue
        return text
