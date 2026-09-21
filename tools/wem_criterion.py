#!/usr/bin/env python3
# Module name: tools/wem_criterion.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""wem_criterion — keeps one distribution's criterion (`tools/dictionary.json`) in step
with the requirement registers and the code, and proves every change with wem_lint.

check  drift in both directions between registers, criterion and code; never writes.
prove  applies a patch to a temporary copy and compares wem_lint runs before and after:
       a patch passes when every expected finding disappears and none is added.
apply  prove, then write — minor version bump, changelog entry naming the authority,
       change record. Without an authority nothing is written (D-03).

Stdlib only (NFRQ-SEC-03), like the lint it drives.
"""

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations

import argparse
import ast
import copy
import datetime as dt
import json
import platform
import re
import subprocess
import sys
import tempfile
import textwrap
from collections import Counter
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

__version__ = "0.2.0"

# Distributions whose tier is stdlib ∪ wattleflow only: a third-party import there
# is a module in the wrong distribution, never a library to allow (CLAUDE.md §7.1).
CLEAN_CORE = frozenset({"wattleflow", "wattleflow-workflow"})
# The lint reads `identifier_acronyms` under this name (wem_lint `_load_registry`).
LINT_ALIASES = {"acronyms": "identifier_acronyms"}
FACETS = ("subjects", "operations", "targets", "qualifiers")
LINT_DRIFT_KINDS = frozenset(
    {"unimplemented-rule", "undeclared-check", "unreadable-severity", "absent-domain"}
)

# --------------------------------------------------------------------------- #
# region Findings                                                             #
# --------------------------------------------------------------------------- #


@dataclass
class Finding:
    direction: str
    kind: str
    subject: str
    evidence: list[str] = field(default_factory=list)
    action: str = ""
    # Who may settle it: "DR", "author", "registers", or "observation".
    authority: str = ""


# --------------------------------------------------------------------------- #
# endregion Findings                                                          #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Criterion                                                            #
# --------------------------------------------------------------------------- #


class Criterion:
    """One distribution's criterion as data."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.raw = path.read_text(encoding="utf-8")
        self.doc: dict[str, Any] = json.loads(self.raw)

    @staticmethod
    def dump(doc: dict[str, Any]) -> str:
        return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"

    @property
    def version(self) -> str:
        return str(self.doc.get("criterion_version", "?"))

    @property
    def distribution(self) -> str:
        return str(self.doc.get("distribution", ""))

    def get(self, key: str, default: Any = None) -> Any:
        return self.doc.get(key, default)

    def key_paths(self) -> set[str]:
        paths: set[str] = set()

        def walk(node: Any, prefix: str) -> None:
            if not isinstance(node, dict):
                return
            for key, value in node.items():
                if key.startswith("_"):
                    continue
                paths.add(prefix + key)
                walk(value, prefix + key + ".")

        walk(self.doc, "")
        return paths

    def checks(self) -> set[str]:
        return {str(rule.get("check")) for rule in self.doc.get("rules") or () if rule.get("check")}

    def libraries(self) -> set[str]:
        scope = self.doc.get("scope") or {}
        allowed = set(scope.get("core_libraries") or ())
        guarded = scope.get("guarded_optional") or {}
        values = guarded.values() if isinstance(guarded, dict) else guarded
        for value in values:
            allowed.update(value if isinstance(value, list) else [value])
        return {str(item) for item in allowed}


def bump_minor(version: str) -> str:
    parts = [int(p) for p in re.findall(r"\d+", version)[:3]] + [0, 0, 0]
    return f"{parts[0]}.{parts[1] + 1}.0"


# --------------------------------------------------------------------------- #
# endregion Criterion                                                         #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Registers                                                            #
# --------------------------------------------------------------------------- #


class Registers:
    """The requirement registers and decision records under a documentation root."""

    KEY_TOKEN = re.compile(r"[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)*")
    ARROW = re.compile(r"dictionary\.json\s*(?:→|->)\s*([a-z_][a-z0-9_.]*)")
    STATUS = re.compile(r"\*\*Status\*\*\s*\|\s*([^|\n]+)")
    ACCEPTED = re.compile(r"prihva[ćc]en|accepted", re.IGNORECASE)

    def __init__(self, root: Path) -> None:
        self.root = root
        # The registers moved under `requirements/` on 2026-09-19; a tree that
        # still carries them at the documentation root keeps being read.
        nested = root / "requirements"
        self.base = nested if nested.is_dir() else root

    def files(self) -> Iterator[Path]:
        yield from sorted(self.base.glob("0[123]-*/*.md"))

    def nfr_ids(self) -> set[str]:
        found = set()
        for path in self.base.glob("03-NFRQ/NFRQ-*.md"):
            match = re.match(r"(NFRQ-[A-Z]+-\d+)", path.name)
            if match:
                found.add(match.group(1))
        return found

    def dr_status(self, dr: str) -> str | None:
        records = sorted(self.base.glob(f"04-DR/{dr}-*.md"))
        if not records:
            return None
        match = self.STATUS.search(records[0].read_text(encoding="utf-8"))
        return match.group(1).strip() if match else "?"

    def cited_keys(self) -> Iterator[tuple[str, str]]:
        """(token, "file:line") for key-shaped names cited after `dictionary.json` on a line.

        Heuristic by construction: prose may name a key the way it names anything
        else, so each hit carries its line for a reviewer to judge.
        """
        for path in self.files():
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                at = line.find("dictionary.json")
                if at < 0:
                    continue
                where = f"{path.relative_to(self.root)}:{number}"
                for token in self.ARROW.findall(line):
                    yield token.rstrip("."), where
                for match in re.finditer(r"`([^`]+)`", line):
                    token = match.group(1)
                    if match.start() <= at or not self.KEY_TOKEN.fullmatch(token):
                        continue
                    if not token.startswith("wattleflow"):
                        yield token, where


# --------------------------------------------------------------------------- #
# endregion Registers                                                         #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Code                                                                 #
# --------------------------------------------------------------------------- #


class Code:
    """What the source tree declares by itself: imports, class names, packages."""

    ACRONYM = re.compile(r"[A-Z]{2,}(?=[A-Z][a-z]|\d|$)")

    def __init__(self, src: Path) -> None:
        self.src = src
        self.imports: dict[str, list[str]] = {}
        self.classes: dict[str, str] = {}
        self.unparsable: list[str] = []
        for path in sorted(src.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            self._read(path)

    def _read(self, path: Path) -> None:
        # Relative to --src, as wem_lint reports locations, so the two can be matched.
        where = str(path.relative_to(self.src))
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            self.unparsable.append(where)
            return
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots = [node.module.split(".")[0]]
            elif isinstance(node, ast.ClassDef):
                self.classes.setdefault(node.name, f"{where}:{node.lineno}")
                continue
            else:
                continue
            for root in roots:
                self.imports.setdefault(root, []).append(f"{where}:{node.lineno}")

    def packages(self) -> set[str]:
        return {p.name for p in self.src.iterdir() if p.is_dir() and p.name != "__pycache__"}

    def pipeline_packages(self) -> set[str]:
        base = self.src / "pipelines"
        if not base.is_dir():
            return set()
        return {p.name for p in base.iterdir() if p.is_dir() and p.name != "__pycache__"}


# --------------------------------------------------------------------------- #
# endregion Code                                                              #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Lint                                                                 #
# --------------------------------------------------------------------------- #


class Lint:
    """wem_lint, run as a person runs it, with its snapshot as the record."""

    def __init__(self, tool: Path, src: Path) -> None:
        self.tool = tool
        self.src = src

    def run(self, criterion: Path) -> dict[str, Any]:
        with tempfile.TemporaryDirectory() as tmp:
            snapshot = Path(tmp) / "vector.json"
            command = [
                sys.executable,
                str(self.tool),
                "--src",
                str(self.src),
                "--registry",
                str(criterion),
                "--snapshot",
                str(snapshot),
                "--no-graph",
                "--no-color",
                "--quiet",
            ]
            result = subprocess.run(command, capture_output=True, text=True, timeout=900)  # noqa: S603
            if not snapshot.exists():
                raise RuntimeError(
                    f"wem_lint wrote no snapshot (exit {result.returncode}): "
                    f"{result.stderr.strip()[-500:]}"
                )
            return json.loads(snapshot.read_text(encoding="utf-8"))

    @staticmethod
    def keys(snapshot: dict[str, Any]) -> Counter:
        return Counter(
            (f.get("kind"), f.get("location"), f.get("name"))
            for f in snapshot.get("findings") or ()
        )


# --------------------------------------------------------------------------- #
# endregion Lint                                                              #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Check                                                                #
# --------------------------------------------------------------------------- #


class Drift:
    """Every direction in which registers, criterion and code disagree."""

    def __init__(self, criterion: Criterion, code: Code, registers: Registers | None) -> None:
        self.criterion = criterion
        self.code = code
        self.registers = registers

    def findings(self, snapshot: dict[str, Any] | None = None) -> list[Finding]:
        out: list[Finding] = []
        if self.registers is not None:
            out += self.registers_to_criterion()
            out += self.criterion_to_registers()
        out += self.code_to_criterion()
        out += self.criterion_to_code()
        if snapshot is not None:
            out += self.criterion_to_tool(snapshot)
        return out

    def registers_to_criterion(self) -> list[Finding]:
        known = self.criterion.key_paths() | self.criterion.checks()
        seen: dict[str, list[str]] = {}
        for token, where in self.registers.cited_keys():
            if token in known or token.split(".")[0] in known and "." not in token:
                continue
            seen.setdefault(token, []).append(where)
        out = []
        for token, where in sorted(seen.items()):
            alias = LINT_ALIASES.get(token)
            out.append(
                Finding(
                    "registers→criterion",
                    "cited-key-missing",
                    token,
                    where,
                    (
                        f"the criterion names it `{alias}` (wem_lint alias) — correct the register"
                        if alias
                        else "the register cites a key the criterion lacks: correct the "
                        "register, or add the key through a DR"
                    ),
                    "registers" if alias else "DR",
                )
            )
        return out

    def criterion_to_registers(self) -> list[Finding]:
        out = []
        known = self.registers.nfr_ids()
        for rule in self.criterion.get("rules") or ():
            nfr = str(rule.get("nfr") or "")
            if nfr.startswith("NFRQ-") and nfr not in known:
                out.append(
                    Finding(
                        "criterion→registers",
                        "rule-nfr-unregistered",
                        f"{rule.get('id')} → {nfr}",
                        [str(self.criterion.path)],
                        "the rule enforces a requirement with no record in 03-NFRQ",
                        "registers",
                    )
                )
        changelog = " ".join(self.criterion.get("_criterion_version") or ())
        for dr in sorted(set(re.findall(r"DR-[A-Z]{3}-\d{3}", changelog))):
            status = self.registers.dr_status(dr)
            if status is not None and self.registers.ACCEPTED.search(status):
                continue
            out.append(
                Finding(
                    "criterion→registers",
                    "change-authority",
                    dr,
                    [str(self.criterion.path)],
                    f"the changelog cites {dr}, status: {status or 'no record'}",
                    "DR",
                )
            )
        return out

    def code_to_criterion(self) -> list[Finding]:
        out = []
        crit = self.criterion
        stdlib = set(sys.stdlib_module_names) | {"__future__", "wattleflow"}
        allowed = crit.libraries()
        clean = crit.distribution in CLEAN_CORE
        for root, where in sorted(self.code.imports.items()):
            if root in stdlib or root in allowed:
                continue
            out.append(
                Finding(
                    "code→criterion",
                    "undeclared-library",
                    root,
                    where[:5],
                    (
                        "a clean-core distribution declares no third-party tier: the module "
                        "belongs to another distribution (NFRQ-SEC-03)"
                        if clean
                        else "add to scope.core_libraries once the dependency is accepted"
                    ),
                    "DR" if clean else "author",
                )
            )

        acronyms = set(crit.get("identifier_acronyms") or ())
        runs: dict[str, list[str]] = {}
        for name, where in self.code.classes.items():
            for run in Code.ACRONYM.findall(name):
                if run not in acronyms:
                    runs.setdefault(run, []).append(f"{name} {where}")
        for run, where in sorted(runs.items()):
            out.append(
                Finding(
                    "code→criterion",
                    "unregistered-acronym",
                    run,
                    where[:5],
                    "register it, or rename — casing is under DR-WFL-004",
                    "DR",
                )
            )

        # 0.2.0: foundation_packages are declared material the lint skips (DR-PRC-008).
        declared = (
            set(crit.get("domains") or ())
            | set(crit.get("foundation_packages") or ())
            | {str(crit.get("shared_namespace") or "")}
        )
        for package in sorted(self.code.packages() - declared):
            out.append(
                Finding(
                    "code→criterion",
                    "undeclared-package",
                    package,
                    [package],
                    "declare it a domain, or record it as foundation material the lint skips",
                    "DR",
                )
            )

        mapped = (
            set((crit.get("package_subject") or {}).keys())
            | set(crit.get("grouping_packages") or ())
            | set(crit.get("exempt_packages") or ())
        )
        for package in sorted(self.code.pipeline_packages() - mapped):
            out.append(
                Finding(
                    "code→criterion",
                    "unmapped-pipeline-package",
                    package,
                    [f"pipelines/{package}"],
                    "a pipeline here passes the name grammar unmeasured: map it to a subject",
                    "DR",
                )
            )
        return out

    def criterion_to_code(self) -> list[Finding]:
        out = []
        names = " ".join(self.code.classes)
        for facet in FACETS:
            for word in sorted(self.criterion.get(facet) or ()):
                # A word ends where a lower-case letter does not follow: `Text` is not `Textile`.
                if not re.search(rf"{re.escape(word)}(?![a-z])", names):
                    out.append(
                        Finding(
                            "criterion→code",
                            "facet-unused",
                            f"{facet}: {word}",
                            [str(self.criterion.path)],
                            "no class name carries it — stale, or reserved ahead of code",
                            "observation",
                        )
                    )
        return out

    @staticmethod
    def criterion_to_tool(snapshot: dict[str, Any]) -> list[Finding]:
        return [
            Finding(
                "criterion→tool",
                str(f.get("kind")),
                str(f.get("name")),
                [str(f.get("location"))],
                str(f.get("message")),
                "DR",
            )
            for f in snapshot.get("findings") or ()
            if f.get("kind") in LINT_DRIFT_KINDS
        ]


# --------------------------------------------------------------------------- #
# endregion Check                                                             #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Patch                                                                #
# --------------------------------------------------------------------------- #


class Patch:
    """Operations on the criterion, with what each must make disappear."""

    OPS = ("add", "remove", "set")

    def __init__(self, data: dict[str, Any]) -> None:
        self.ops: list[dict[str, Any]] = list(data.get("ops") or ())
        self.expect: list[dict[str, str]] = list(data.get("expect") or ())
        self.reason: str = str(data.get("reason") or "").strip()
        if not self.ops:
            raise ValueError("a patch needs at least one op")
        for op in self.ops:
            if op.get("op") not in self.OPS or not op.get("path"):
                raise ValueError(f"invalid op {op!r}: op must be one of {self.OPS}, with a path")

    @classmethod
    def load(cls, path: Path) -> Patch:
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def apply_to(self, doc: dict[str, Any]) -> dict[str, Any]:
        result = copy.deepcopy(doc)
        for op in self.ops:
            *parents, key = str(op["path"]).split(".")
            node = result
            for part in parents:
                node = node[part]
            if op["op"] == "set":
                node[key] = op.get("value")
                continue
            target = node[key]
            if not isinstance(target, list):
                raise ValueError(f"{op['path']} is not a list")
            if op["op"] == "add":
                if op.get("value") in target:
                    raise ValueError(f"{op['value']!r} already in {op['path']}")
                target.append(op.get("value"))
            else:
                if op.get("value") not in target:
                    raise ValueError(f"{op['value']!r} not in {op['path']}")
                target.remove(op.get("value"))
        return result

    def expected(self, key: tuple) -> bool:
        kind, location, name = key
        return any(
            e.get("kind") == kind and e.get("match", "") in f"{location} {name}"
            for e in self.expect
        )


def propose(findings: list[Finding]) -> dict[str, Any] | None:
    """The mechanical part of the report as a patch; everything else needs a decision."""
    ops, expect = [], []
    for f in findings:
        if f.kind == "undeclared-library" and f.authority == "author":
            ops.append({"op": "add", "path": "scope.core_libraries", "value": f.subject})
            for where in f.evidence:
                expect.append({"kind": "foreign-import", "match": where.split(":")[0]})
    if not ops:
        return None
    libraries = ", ".join(op["value"] for op in ops)
    return {"reason": f"scope.core_libraries gains {libraries}.", "ops": ops, "expect": expect}


# --------------------------------------------------------------------------- #
# endregion Patch                                                             #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Prove and apply                                                      #
# --------------------------------------------------------------------------- #


def platform_name() -> str:
    return f"Python {platform.python_version()} · {platform.system()} {platform.release()}"


def prove(criterion: Criterion, patch: Patch, lint: Lint) -> dict[str, Any]:
    before = lint.run(criterion.path)
    patched = patch.apply_to(criterion.doc)
    with tempfile.TemporaryDirectory() as tmp:
        copy_path = Path(tmp) / "dictionary.json"
        copy_path.write_text(Criterion.dump(patched), encoding="utf-8")
        after = lint.run(copy_path)
    old, new = Lint.keys(before), Lint.keys(after)
    removed, added = old - new, new - old
    missing = [
        e for e in patch.expect if not any(patch.expected(k) and k[0] == e["kind"] for k in removed)
    ]
    return {
        "passed": not added and not missing,
        "removed": [list(k) for k in sorted(removed.elements(), key=str)],
        "added": [list(k) for k in sorted(added.elements(), key=str)],
        "expected_not_removed": missing,
        "before": before.get("reproducibility_triple"),
        "after": after.get("reproducibility_triple"),
    }


def apply(
    criterion: Criterion,
    patch: Patch,
    lint: Lint,
    authority: str,
    record_dir: Path | None,
    today: str,
) -> dict[str, Any]:
    if not authority.strip():
        raise PermissionError(
            "no authority: a criterion change needs a DR or the author's instruction"
        )
    if Criterion.dump(criterion.doc) != criterion.raw:
        raise ValueError(
            "the criterion is not in canonical JSON form; writing it would reformat it"
        )
    proof = prove(criterion, patch, lint)
    if not proof["passed"]:
        raise ValueError(f"the patch did not prove: {json.dumps(proof, ensure_ascii=False)[:800]}")

    doc = patch.apply_to(criterion.doc)
    old = criterion.version
    new = bump_minor(old)
    doc["criterion_version"] = new
    summary = (
        f"{new} ({today}) — {patch.reason} Authority: {authority}. Proven by wem_criterion "
        f"{__version__}: {len(proof['removed'])} finding(s) removed, none added."
    )
    doc["_criterion_version"] = textwrap.wrap(summary, 78) + list(
        doc.get("_criterion_version") or ()
    )
    criterion.path.write_text(Criterion.dump(doc), encoding="utf-8")

    record = {
        "kind": "change-set",
        "id": f"CHG-CRITERION-{today}-{new}",
        "date": today,
        "title": f"Criterion {old} → {new} ({criterion.distribution})",
        "status": "applied",
        "language": "en",
        "authored_by": f"wem_criterion {__version__}",
        "governance": {"authority": authority, "reason": patch.reason},
        "changes": patch.ops,
        "verification": proof,
        "reproducibility": {
            "tool": f"wem_criterion {__version__}",
            "lint": str(lint.tool),
            "criterion": str(criterion.path),
            "src": str(lint.src),
            "platform": platform_name(),
        },
    }
    if record_dir is not None:
        record_dir.mkdir(parents=True, exist_ok=True)
        out = record_dir / f"{today}-criterion-{new}.json"
        out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        record["path"] = str(out)
    return record


# --------------------------------------------------------------------------- #
# endregion Prove and apply                                                   #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region CLI                                                                  #
# --------------------------------------------------------------------------- #


def triple(criterion: Criterion, src: Path, docs: Path | None) -> dict[str, str]:
    return {
        "tool": f"wem_criterion {__version__}",
        "criterion": f"{criterion.path} {criterion.version}",
        "source": str(src),
        "registers": str(docs) if docs else "not read",
        "platform": platform_name(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("mode", choices=("check", "prove", "apply"))
    parser.add_argument("--criterion", type=Path, required=True)
    parser.add_argument("--src", type=Path, required=True, help="the wattleflow package root")
    parser.add_argument("--docs", type=Path, help="documentation root (registers)")
    parser.add_argument("--lint", type=Path, help="wem_lint.py; required for prove/apply")
    parser.add_argument("--patch", type=Path)
    parser.add_argument("--authority", default="")
    parser.add_argument("--record", type=Path, help="directory for the change record")
    parser.add_argument("--out", type=Path, help="write the report as JSON")
    parser.add_argument("--propose", type=Path, help="write the mechanical patch (check)")
    parser.add_argument("--date", default=dt.date.today().isoformat())
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)

    criterion = Criterion(args.criterion)
    lint = Lint(args.lint, args.src) if args.lint else None

    if args.mode == "check":
        snapshot = lint.run(criterion.path) if lint else None
        registers = Registers(args.docs) if args.docs else None
        findings = Drift(criterion, Code(args.src), registers).findings(snapshot)
        report = {
            "reproducibility_triple": triple(criterion, args.src, args.docs),
            "counts": dict(Counter(f"{f.direction} · {f.kind}" for f in findings)),
            "findings": [asdict(f) for f in findings],
            "blind_spots": [
                "cited-key-missing is a heuristic over prose; each hit carries its line",
                "severity agreement between an NFRQ criterion and its rule is not read",
                "dynamic imports and YAML-declared types are invisible to the AST",
            ],
        }
        for f in findings:
            print(f"[{f.direction}] {f.kind}: {f.subject} — {f.action} ({f.authority})")
        print(
            f"wem_criterion: {len(findings)} finding(s) · "
            f"{report['reproducibility_triple']['criterion']}"
        )
        if args.out:
            args.out.write_text(
                json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
        if args.propose:
            patch = propose(findings)
            if patch:
                args.propose.write_text(
                    json.dumps(patch, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
                )
                print(f"wem_criterion: patch proposed in {args.propose}")
        return 0

    if lint is None or args.patch is None:
        parser.error(f"{args.mode} needs --lint and --patch")
    patch = Patch.load(args.patch)
    try:
        if args.mode == "prove":
            result = prove(criterion, patch, lint)
        else:
            result = apply(criterion, patch, lint, args.authority, args.record, args.date)
    except (PermissionError, ValueError, KeyError, RuntimeError) as e:
        print(f"wem_criterion: {args.mode} refused — {e}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if args.out:
        args.out.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    return 0 if args.mode == "apply" or result["passed"] else 1


# --------------------------------------------------------------------------- #
# endregion CLI                                                               #
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    sys.exit(main())
