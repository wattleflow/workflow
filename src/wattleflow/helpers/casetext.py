# Module Name: helpers/casetext.py
# Description: This modul contains a simple case text format class.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence


class CaseText(str):
    def __format__(self, spec: str) -> str:
        if spec == "upper":
            return self.upper()
        if spec == "lower":
            return self.lower()
        if spec in ("title", "capitalize"):
            return self.title()
        return super().__format__(spec)
