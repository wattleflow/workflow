# Module name: tools/wem_lint.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""wem_lint — static enforcement of the Wattleflow NFR registry.

Implements the machine-verifiable acceptance criteria of:
  * NFR-ORG-01 — Dependency Locality of Support Classes (import-graph checks)
  * NFR-ORG-02 — Class Nomenclature (name-grammar checks)
  * NFR-ORG-03 — TypeVar Nomenclature (generic-parameter role names)
  * NFR-ORG-07 — Preset whitelist declaration (`ALLOWED` as a class attribute)
  * NFR-SEC-03 — Supply-chain trust & distribution locality (tier + manifest)

The checks themselves are purely AST/import-graph based — a measured module is
never imported *to be checked*, so a syntactically broken target yields findings
rather than a crash. It is not true that no measured module is imported at all:
the tool is built on `wattleflow.concrete`, which is itself a measured domain
(see the self-reference below). It is runnable on demand now and, once a CI
pipeline exists, as a quality gate. Runtime dependencies: none beyond the
standard library and this distribution's own `wattleflow.core` +
`wattleflow.concrete`. The criterion is read from `tools/dictionary.json` of the
INVOKED distribution — JSON, not YAML, so a quality gate never depends on a
third-party parser being installed. Severity and waiver come from that
criterion's `rules` block, not from constants here, so the enforcement level
stays under DR governance. Report strings live in `tools/messages.json` next to
the tool (a criterion may still carry them inline); `report_language` picks the
default (en) and --lang overrides it per run.

The tool dogfoods the framework it checks (self-reference — `dictionary.yaml:
wem-lint`), consuming both distributions:
  * Iterator/Aggregate (ISyncAggregate, LazyIterator) — SourceTree walks the .py tree
  * Builder (IBuilder)                                — ImportGraphBuilder (ORG-01)
  * Strategy/Context (IStrategy, IStrategyContext)    — one rule per NFR, run by WemLint
  * Factory (IFactory)                                — RuleFactory maps an NFR id to its rule
  * Identity (Wattleflow)                             — the root `name` contract

Consequence of the self-reference: the lint cannot run against a concrete/ layer
that does not import. That is deliberate and declared, not a defect — the
instrument shares the fate of what it measures.

Usage:
    python tools/wem_lint.py [--src SRC] [--registry FILE] [--quiet] [--select IDS]
    # the ORG-01 dependency graph renders by default; suppress it with --no-graph
    python tools/wem_lint.py --no-graph
    python tools/wem_lint.py --graph ascii [--graph-out FILE] [--no-color]
    # from code: raise SystemExit(Application(argv).run())

Exit code is non-zero if any ERROR-level violation is found (WARNING/INFO do not
fail the build — tolerated legacy is reported, not blocked; see NFR.md).
"""

from __future__ import annotations
import argparse
import ast
import fnmatch
import json
import logging
import os
import platform
import re
import sys
import tomllib

from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Iterator

_STDLIB = set(sys.stdlib_module_names)
_TOOL_HOME = Path(__file__).resolve().parent
_CALL_HOME = Path(__file__).absolute().parent
for _src_root in (_CALL_HOME.parent / "src", _TOOL_HOME.parent / "src"):
    if _src_root.is_dir() and str(_src_root) not in sys.path:
        sys.path.insert(0, str(_src_root))

try:
    from wattleflow.core import (
        IBuilder,
        IFactory,
        IStrategy,
        IStrategyContext,
        ISyncAggregate,
        IWattleflow,
    )
except ImportError as e:  # pragma: no cover
    sys.exit(f"wem_lint requires the 'wattleflow' core package (import failed: {e})")


try:
    from wattleflow.concrete import LazyIterator, Wattleflow
except ImportError as e:  # pragma: no cover
    sys.exit(
        f"wem_lint requires wattleflow.concrete (import failed: {e})\n"
        "The lint is built on the layer it measures; a broken concrete/ layer must be "
        "repaired before conformance can be assessed."
    )

# CamelCase tokeniser that keeps acronyms whole: "PDFExtractText" -> [PDF, Extract, Text]
_CAMEL = re.compile(r"[A-Z]+(?![a-z])|[A-Z][a-z]+|[A-Z]|\d+")

# Criterion-versioning convention (METHODOLOGY §1 t.2): a change in rule
# semantics or in the criterion source is a minor bump, because the same code
# can yield a different vector afterwards.
__version__ = "1.12.0"
ERROR, WARNING, INFO = logging.ERROR, logging.WARNING, logging.INFO


# --------------------------------------------------------------------------- #
# region Findings                                                             #
# --------------------------------------------------------------------------- #
class Finding:
    # `kind` keys the friendly-report catalogue (explanation printed once per kind);
    # `detail` is the compact one-line fact shown per instance under that heading.
    __slots__ = ("nfr", "severity", "path", "line", "name", "message", "kind", "detail")

    def __init__(self, nfr, severity, path, line, name, message, kind=None, detail=None):
        self.nfr = nfr
        self.severity = severity
        self.path = path
        self.line = line
        self.name = name
        self.message = message
        self.kind = kind
        self.detail = detail

    def render(self, root: Path) -> str:
        try:
            rel = self.path.relative_to(root)
        except ValueError:
            rel = self.path
        level = logging.getLevelName(self.severity)
        return f"  [{level:<7}] {rel}:{self.line}  {self.name}\n           {self.message}"


# --------------------------------------------------------------------------- #
# endregion Findings                                                          #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Source file — one parse per module, shared by every rule             #
# --------------------------------------------------------------------------- #
class SourceFile:
    """A module read and parsed once per run, then shared."""

    _CACHE: dict[Path, "SourceFile"] = {}
    __slots__ = ("path", "tree", "error", "_foreign", "_imports")

    def __init__(self, path: Path):
        self.path = path
        self.error: SyntaxError | None = None
        self.tree: ast.Module | None = None
        self._foreign: dict[frozenset, set[str]] = {}
        self._imports: tuple[str, ...] | None = None
        try:
            self.tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as e:
            self.error = e

    @classmethod
    def of(cls, path: Path) -> "SourceFile":
        cached = cls._CACHE.get(path)
        if cached is None:
            cached = cls._CACHE[path] = SourceFile(path)
        return cached

    def imported_modules(self) -> tuple[str, ...]:
        """Every module name this file imports, in source order.

        ast.walk (not just tree.body) is deliberate: a lazy, in-function import
        still fixes the module's home distribution (DR-WFL-002 §2.1), so it must
        count exactly like a module-level one.
        """
        if self._imports is None:
            names: list[str] = []
            for node in ast.walk(self.tree) if self.tree else ():
                if isinstance(node, ast.Import):
                    names += [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    names.append(node.module)
            self._imports = tuple(names)
        return self._imports

    def foreign_roots(self, core_libs: frozenset[str]) -> set[str]:
        # Root packages imported from outside (stdlib ∪ wattleflow ∪ core_libs) —
        # the third-party libraries that place a module outside this distribution.
        cached = self._foreign.get(core_libs)
        if cached is None:
            allowed = _STDLIB | {"wattleflow"} | set(core_libs)
            cached = self._foreign[core_libs] = {
                top
                for module in self.imported_modules()
                if (top := module.split(".")[0]) and top not in allowed
            }
        return cached


# --------------------------------------------------------------------------- #
# endregion Source file                                                       #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Naming — name & layout primitives                                    #
# --------------------------------------------------------------------------- #
class Naming:
    """Stateless primitives for analysing class names and module layout.

    A bare `Helper`/`Utility` name is intentionally avoided: NFR-ORG-02 — the very
    rule this tool enforces — prohibits standalone generic role nouns.
    """

    @staticmethod
    def tokenize(name: str) -> list[str]:
        return _CAMEL.findall(name)

    @staticmethod
    def casefold_lookup(token: str, vocab) -> str | None:
        cf = token.casefold()
        for v in vocab:
            if v.casefold() == cf:
                return v
        return None

    @staticmethod
    def file_domain(path: Path, src: Path, domains: set[str], shared: str) -> str | None:
        # First path component under src/wattleflow → domain (or the shared namespace).
        try:
            parts = path.relative_to(src).parts
        except ValueError:
            return None
        if not parts:
            return None
        top = parts[0]
        if top in domains or top == shared:
            return top
        return None

    @staticmethod
    def class_subpackage(path: Path, src: Path, domain: str) -> str | None:
        # Component immediately after the domain, if the class lives in a sub-package.
        parts = path.relative_to(src).parts
        if len(parts) >= 3 and parts[0] == domain:
            return parts[1]
        return None  # class sits directly in the domain package

    @staticmethod
    def foreign_imports(path: Path, core_libs: frozenset[str]) -> set[str]:
        return SourceFile.of(path).foreign_roots(core_libs)


class Criterion:
    """The registry's `rules` block — declared severity and waiver per check.

    Severity belongs to the criterion, which is versioned apart from this tool
    (POLICY §9), so it is resolved from the registry instead of being a constant
    at the emission site. `IMPLEMENTED` is the other half of the same contract:
    it names, per declared check, the finding kinds this tool can actually emit,
    which makes drift between registry and instrument measurable rather than
    assumed.
    """

    LEVELS = {"error": ERROR, "warning": WARNING, "info": INFO}

    # `acronym_identifier_casing.status` values that put criterion 4 in force.
    # The Croatian form is accepted because the discourse registry the criterion
    # was cut from still carries its own status vocabulary.
    ADOPTED = frozenset({"adopted", "usvojen"})

    # registry `check` → finding kinds emitted for it
    IMPLEMENTED = {
        "domain_acyclicity": ("import-cycle", "wrong-direction-import", "misfiled-leaf"),
        "helper_fan_in": ("single-consumer-helper",),
        "base_family_membership": ("pipeline-grammar",),
        "prohibited_standalone": ("standalone-role-noun",),
        "acronym_case": ("acronym-case",),
        "typevar_role_vocabulary": ("typevar-role",),
        "clean_core_imports": ("foreign-import",),
        "distribution_manifest": ("manifest-no-namespaces", "manifest-excluded-package"),
        "preset_allowed_declaration": (
            "preset-allowed-name",
            "preset-allowed-scope",
            "preset-allowed-forwarded",
        ),
    }

    @classmethod
    def severity(cls, reg: dict, check: str, default: int = ERROR) -> int:
        for rule in reg.get("rules") or ():
            if rule.get("check") == check:
                declared = str(rule.get("severity", "")).lower()
                return cls.LEVELS.get(declared, default)
        return default

    @classmethod
    def acronym_severity(cls, reg: dict) -> int:
        """The single resolution path for the acronym-casing level.

        Two registry keys used to answer this — `acronym_identifier_casing.status`
        (which the tool read) and the `acronym_case` rule severity (which it did
        not) — so a DR editing the rule table would have been silently ignored on
        precisely the rule that is under an open DR. Precedence is now declared:
        an adopted status puts criterion 4 in force; while the decision is open
        the rule severity applies but cannot exceed WARNING, because enforcing
        one side of an undecided question is what METHODOLOGY §9 forbids.
        """
        status = str((reg.get("acronym_identifier_casing") or {}).get("status", "")).lower()
        if status in cls.ADOPTED:
            return ERROR
        return min(cls.severity(reg, "acronym_case", WARNING), WARNING)

    @classmethod
    def absent_domains(cls, reg: dict, src: Path, present: set[str]) -> list[Finding]:
        # Drift in the third direction: a domain the criterion declares but no
        # module under --src belongs to. Rules scoped to it then measure nothing
        # at all, and the vector reads as coverage it never had (D-11).
        out: list[Finding] = []
        for domain in sorted(set(reg.get("domains") or ()) - present):
            out.append(
                Finding(
                    "EXC",
                    INFO,
                    src / domain,
                    0,
                    domain,
                    "declared as a domain in the criterion, but no module under --src "
                    "belongs to it — either it moved to another distribution and the "
                    "criterion was not revised, or --src is mis-pointed",
                    kind="absent-domain",
                    detail=f"no module under {src.name}/{domain}",
                )
            )
        return out

    @classmethod
    def drift(cls, reg: dict, src: Path) -> list[Finding]:
        # Three directions, all silent until now: a rule the registry declares but
        # no code path can raise (its severity and waiver are decoration), a check
        # this tool emits that the registry never declared (it escapes DR governance
        # of severity/waiver entirely), and a severity word the tool cannot read —
        # which fell back to a constant here, i.e. to the level the registry was
        # supposed to be deciding.
        declared = {r.get("check"): r for r in reg.get("rules") or () if r.get("check")}
        out: list[Finding] = []
        for check, rule in sorted(declared.items()):
            word = str(rule.get("severity", ""))
            if word.lower() in cls.LEVELS:
                continue
            out.append(
                Finding(
                    "EXC",
                    INFO,
                    src,
                    0,
                    f"{rule.get('id', '?')} · {check}",
                    f"severity '{word}' is not one of {', '.join(cls.LEVELS)} — the tool "
                    "cannot read it and falls back to its own default, so this rule's "
                    "enforcement level is decided by the instrument, not by the criterion",
                    kind="unreadable-severity",
                    detail=f"{rule.get('id', '?')} · {check}: severity={word!r}",
                )
            )
        for check in sorted(set(declared) - set(cls.IMPLEMENTED)):
            rule = declared[check]
            out.append(
                Finding(
                    "EXC",
                    INFO,
                    src,
                    0,
                    f"{rule.get('id', '?')} · {check}",
                    f"declared in the registry (severity={rule.get('severity')}, "
                    f"waiver={rule.get('waiver')}) but no check implements it — "
                    "the criterion promises a verdict the instrument cannot give",
                    kind="unimplemented-rule",
                    detail=(
                        f"{rule.get('id', '?')} · {check} "
                        f"(severity={rule.get('severity')}, waiver={rule.get('waiver')})"
                    ),
                )
            )
        for check in sorted(set(cls.IMPLEMENTED) - set(declared)):
            out.append(
                Finding(
                    "EXC",
                    INFO,
                    src,
                    0,
                    check,
                    "emitted by this tool but absent from the registry `rules` block — "
                    "its severity and waiver are outside DR governance",
                    kind="undeclared-check",
                    detail=f"{check} → emits: {', '.join(cls.IMPLEMENTED[check])}",
                )
            )
        return out


# --------------------------------------------------------------------------- #
# endregion Naming — name & layout primitives                                 #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Source tree — Iterator / Aggregate (ISyncAggregate, IIterator)       #
# --------------------------------------------------------------------------- #
class PyFileIterator(LazyIterator[Path]):
    """Yields every non-cache, in-scope .py file under a root, in stable order.

    Since core v0.0.0.46 IIterator declares create_iterator() only; the lazy
    build-on-first-__next__ machinery is the concrete LazyIterator policy.
    """

    def __init__(self, root: Path, exclude: frozenset[Path] = frozenset()):
        super().__init__()
        self._root = root
        self._exclude = exclude

    def create_iterator(self) -> Iterator[Path]:
        for path in sorted(self._root.rglob("*.py")):
            if "__pycache__" in path.parts or path in self._exclude:
                continue
            yield path


class SourceTree(Wattleflow, ISyncAggregate[Path]):
    """Aggregate over the source tree; hands out fresh file iterators."""

    def __init__(self, root: Path, exclude: frozenset[Path] = frozenset()):
        super().__init__()
        self._root = root
        self._exclude = exclude

    def create_iterator(self) -> PyFileIterator:
        return PyFileIterator(self._root, self._exclude)


# --------------------------------------------------------------------------- #
# endregion Source tree — Iterator / Aggregate (ISyncAggregate, IIterator)    #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region NFR-ORG-02 — Class Nomenclature                                      #
# --------------------------------------------------------------------------- #
class NomenclatureRule(Wattleflow, IStrategy):
    """NFR-ORG-02 — class-name grammar.

    Two scopes, deliberately different (analysis 2026-07-31, N-04):
      * criterion 6 (no standalone generic role noun) applies to EVERY class in
        every domain and the shared namespace, nested ones included — NFR-ORG-02
        scopes it that way and NFR-ORG-04 §3 / NFR-ORG-05 delegate to it. Until
        v1.11.0 the whole rule short-circuited on `domain != "pipelines"`, so in a
        distribution without a `pipelines` domain it enforced nothing while the
        vector still read green.
      * the `Pipeline<Subject><Operation>` grammar applies to the `pipelines`
        domain and needs the processors vocabulary (`subjects`); a criterion that
        declares neither opts out of that half, and says so in `blind_spots`.
    """

    def execute(self, caller: IWattleflow, *, src, reg, source, **kwargs) -> list[Finding]:
        findings: list[Finding] = []
        for path in source.create_iterator():
            self._check_file(path, src, reg, findings)
        return findings

    def _check_file(self, path, src, reg, findings):
        domain = Naming.file_domain(path, src, set(reg["domains"]), reg["shared_namespace"])
        if domain is None:
            return

        def add(sev, line, nm, msg, kind=None):
            findings.append(Finding("ORG-02", sev, path, line, nm, msg, kind=kind))

        # Severity is a registry fact, not a constant here (POLICY §9).
        grammar_sev = Criterion.severity(reg, "base_family_membership", ERROR)
        standalone_sev = Criterion.severity(reg, "prohibited_standalone", ERROR)

        tree = SourceFile.of(path).tree
        if tree is None:
            return  # unparsable — WemLint raises it once, for every rule at once

        # Criterion 6 — every class, every domain, nested included.
        prohibited = set(reg.get("prohibited_standalone", []))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name in prohibited:
                add(
                    standalone_sev,
                    node.lineno,
                    node.name,
                    "standalone generic role noun — must be domain-qualified (criterion 6)",
                    kind="standalone-role-noun",
                )

        if domain != "pipelines":
            return

        # `bases` is a family→[bases] map; pipeline detection reads the pipeline
        # family (older registries used a flat `pipeline_bases` list).
        pipeline_bases = reg.get("bases", {}).get("pipeline") or reg.get("pipeline_bases", [])
        bases = set(pipeline_bases)
        subpkg = Naming.class_subpackage(path, src, "pipelines")
        canon_pkg = reg.get("package_aliases", {}).get(subpkg, subpkg)

        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            is_pipeline = bool({b.id for b in node.bases if isinstance(b, ast.Name)} & bases)
            has_prefix = node.name.startswith("Pipeline")

            if has_prefix and not is_pipeline:
                add(
                    grammar_sev,
                    node.lineno,
                    node.name,
                    "`Pipeline` prefix on a non-pipeline class (criterion 2)",
                    kind="pipeline-grammar",
                )
            if not is_pipeline:
                continue
            if not has_prefix:
                add(
                    grammar_sev,
                    node.lineno,
                    node.name,
                    "pipeline class must carry the `Pipeline` prefix (criterion 2)",
                    kind="pipeline-grammar",
                )
                continue
            if canon_pkg in reg.get("exempt_packages", []):
                add(
                    INFO,
                    node.lineno,
                    node.name,
                    f"package '{subpkg}' is exempt (deferred via DR) — grammar not enforced",
                    kind="exempt-package",
                )
                continue
            if subpkg in reg.get("package_aliases", {}):
                add(
                    WARNING,
                    node.lineno,
                    node.name,
                    f"package '{subpkg}' should be renamed to canonical '{canon_pkg}' (decision 2)",
                    kind="package-alias",
                )

            self._check_grammar(node, path, reg, canon_pkg, findings)

    def _check_grammar(self, node, path, reg, canon_pkg, findings):
        # The Subject/Operation grammar is a processors-only vocabulary; a registry
        # that does not declare it (e.g. clean-core workflow) opts out of the check.
        if not reg.get("subjects"):
            return
        name = node.name
        segs = Naming.tokenize(name[len("Pipeline") :])
        subjects, operations = reg["subjects"], reg.get("operations", [])
        targets, qualifiers = reg.get("targets", []), reg.get("qualifiers", [])
        acronyms, synonyms = reg.get("acronyms", []), reg.get("synonyms", {})
        # Registry-driven, like ORG-03: the enforcement level is a fact of the
        # criterion, not a constant of the tool — and it is resolved in one place.
        casing_sev = Criterion.acronym_severity(reg)
        casing_pending = reg.get("acronym_pending", "an open DR")
        casing_note = (
            "criterion 4"
            if casing_sev == ERROR
            else f"undecided ({casing_pending} pending); waiver declared, not enforced"
        )

        def add(sev, msg, kind="pipeline-grammar"):
            findings.append(Finding("ORG-02", sev, path, node.lineno, name, msg, kind=kind))

        # 1) Subject — longest leading run of segments that joins to a known subject.
        subject, used = None, 0
        for i in range(len(segs), 0, -1):
            if "".join(segs[:i]) in subjects:
                subject, used = "".join(segs[:i]), i
                break
        if subject is None:
            cf = Naming.casefold_lookup(segs[0], subjects) if segs else None
            if cf:
                add(
                    casing_sev,
                    f"subject '{segs[0]}' casing differs from '{cf}' — {casing_note}",
                    kind="acronym-case",
                )
                subject, used = cf, 1
            else:
                trailing = next((s for s in segs if Naming.casefold_lookup(s, subjects)), None)
                hint = f"; subject '{trailing}' appears trailing — lead with it" if trailing else ""
                add(ERROR, f"no registered Subject at the front (criterion 1){hint}")
                return

        # 5) Subject must equal the owning package's canonical subject.
        expected = reg.get("package_subject", {}).get(canon_pkg)
        if expected is not None and subject.casefold() != expected.casefold():
            add(ERROR, f"Subject '{subject}' != package subject '{expected}' (criterion 5)")
        elif expected is None and canon_pkg in reg.get("grouping_packages", []):
            add(
                WARNING,
                f"package '{canon_pkg}' groups several subjects — "
                "subject/package relaxed (pending ADR)",
            )

        # 2) Operation or To<Target>.
        tail = segs[used:]
        if not tail:
            add(ERROR, "missing Operation or To<Target> (criterion 1)")
            return
        if tail[0] == "To":
            target = tail[1] if len(tail) > 1 else ""
            if target not in targets:
                add(ERROR, f"unknown converter Target 'To{target}' (criterion 3)")
            tail = tail[2:]
        elif tail[0] in operations:
            tail = tail[1:]
        else:
            canon = synonyms.get(tail[0])
            if canon:
                add(ERROR, f"Operation '{tail[0]}' is a synonym — use '{canon}' (criterion 3, DRY)")
            else:
                add(ERROR, f"Operation '{tail[0]}' not in the closed verb vocabulary (criterion 3)")
            tail = tail[1:]

        # 3) Remaining segments must be registered qualifiers.
        for q in tail:
            if q in qualifiers:
                continue
            cf = Naming.casefold_lookup(q, acronyms)
            if cf and cf != q:
                add(
                    casing_sev,
                    f"acronym '{q}' casing differs from '{cf}' — {casing_note}",
                    kind="acronym-case",
                )
            else:
                add(WARNING, f"qualifier '{q}' not registered (extend via ADR, criterion 3)")


# --------------------------------------------------------------------------- #
# endregion NFR-ORG-02 — Class Nomenclature                                   #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region NFR-ORG-01 — Dependency Locality                                     #
# --------------------------------------------------------------------------- #
class ImportGraphBuilder(Wattleflow, IBuilder):
    """Builds the shared-helper fan-in graph and collects acyclicity violations."""

    def __init__(self, src, reg):
        super().__init__()
        self._src = src
        self._reg = reg
        self._domains = set(reg["domains"])
        self._shared = reg["shared_namespace"]
        self._fanin: dict[str, set[str]] = defaultdict(set)  # helper module -> {domains}
        # Directional edge stores so violations can be classified in a post-pass:
        self._helper_to_domain: list[tuple] = []  # (path, line, target, module, names)
        self._domain_to_helper: dict[str, list[tuple]] = defaultdict(
            list
        )  # src module -> [(path, line)]
        self._imports_wf: set[str] = set()  # packages that import anything from wattleflow
        self.edges: list[
            tuple
        ] = []  # (src_pkg, dst_pkg, dst_module, names, path, line) — for graphs

    def _module_of(self, path: Path) -> str | None:
        # Dotted module name of a file, so reverse edges key by the exact module (not just
        # the package): concrete.exception importing back into helpers is a cycle; a sibling
        # concrete.logger that does not is only a layering breach.
        try:
            parts = path.relative_to(self._src).with_suffix("").parts
        except ValueError:
            return None
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        return ".".join(("wattleflow",) + parts)

    def add(self, path: Path) -> None:
        dom = Naming.file_domain(path, self._src, self._domains, self._shared)
        if dom is None:
            return
        tree = SourceFile.of(path).tree
        if tree is None:
            return
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                names = [a.name for a in node.names]
                self._record_edge(node.module, dom, path, node.lineno, names)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    self._record_edge(alias.name, dom, path, node.lineno, [])

    def build(self) -> dict[str, set[str]]:
        return self._fanin

    def _record_edge(self, module, dom, path, line, names) -> None:
        parts = module.split(".")
        if len(parts) < 2 or parts[0] != "wattleflow":
            return
        target = parts[1]
        self._imports_wf.add(dom)  # this package has an intra-project dependency → not a pure leaf
        self.edges.append((dom, target, module, tuple(names), path, line))
        if target == self._shared and len(parts) >= 3 and dom != self._shared:
            self._fanin[parts[2]].add(dom)  # domain importing a shared helper → fan-in
            src_module = self._module_of(path)  # reverse edge, keyed by the importing module
            if src_module:
                self._domain_to_helper[src_module].append((path, line))
        elif target in self._domains and dom == self._shared:
            self._helper_to_domain.append((path, line, target, module, tuple(names)))

    def _classify(self):
        # Yields (path, line, target_pkg, tag, note, message) per helper→domain edge. A CYCLE is
        # when that exact module imports back into helpers, a LEAF breach when the target imports
        # nothing from wattleflow (misfiled as a domain), else a one-way LAYERING breach. Shared by
        # violations() (Findings) and graph() (edge colouring), so both stay in step.
        pure_leaves = self._domains - self._imports_wf
        for path, line, target, module, names in self._helper_to_domain:
            sym = ", ".join(names) if names else module.rsplit(".", 1)[-1]
            reverse = self._domain_to_helper.get(module)
            if reverse:
                rp, rl = reverse[0]
                try:
                    rel = rp.relative_to(self._src)
                except ValueError:
                    rel = rp
                tag, note = "CYCLE", f"back-edge: {rel}:{rl}"
                detail = f"imports {sym} from '{module}' — loop back at {rel}:{rl}"
                msg = (
                    f"imports {sym} from '{module}' — MUTUAL CYCLE: domain '{target}' imports back "
                    f"into helpers at {rel}:{rl} — breaks acyclicity (criterion 3); "
                    "relocate the symbol to a leaf tier"
                )
            elif target in pure_leaves:
                tag, note = "LEAF", "pure leaf → make it foundational, not a domain"
                detail = f"imports {sym} from '{module}' ('{target}' imports nothing itself)"
                msg = (
                    f"imports {sym} from '{module}' — '{target}' is a pure leaf (imports nothing "
                    "from wattleflow); reclassify as foundational, not a domain (criterion 3)"
                )
            else:
                tag, note = "LAYERING", "one-way breach → relocate the symbol"
                detail = f"imports {sym} from '{module}'"
                msg = (
                    f"imports {sym} from '{module}' — one-way layering breach, no reverse edge; "
                    "relocate the symbol to a leaf tier (criterion 3)"
                )
            yield path, line, target, tag, note, msg, detail

    # tag → catalogue kind (friendly report groups by this)
    _KIND = {"CYCLE": "import-cycle", "LAYERING": "wrong-direction-import", "LEAF": "misfiled-leaf"}

    def violations(self) -> list[Finding]:
        severity = Criterion.severity(self._reg, "domain_acyclicity", ERROR)
        return [
            Finding(
                "ORG-01",
                severity,
                path,
                line,
                f"helpers→{target} [{tag}]",
                msg,
                kind=self._KIND[tag],
                detail=detail,
            )
            for path, line, target, tag, note, msg, detail in self._classify()
        ]

    def graph(self):
        # Package-level adjacency + a violation map keyed (src_pkg, dst_pkg) → {tags, notes},
        # so the renderer can draw the DAG and colour the offending edges.
        nodes: set[str] = set()
        adj: dict[str, set[str]] = defaultdict(set)
        for src, dst, *_ in self.edges:
            if src == dst:
                continue  # intra-package self-loop — noise for a package-level DAG
            nodes.update((src, dst))
            adj[src].add(dst)
        scope = self._domains | {self._shared}  # packages actually walked as import sources
        viol: dict[tuple, dict] = defaultdict(lambda: {"tags": set(), "notes": []})
        for _, _, target, tag, note, _, _ in self._classify():
            v = viol[(self._shared, target)]
            v["tags"].add(tag)
            if note not in v["notes"]:
                v["notes"].append(note)
        return nodes, adj, viol, scope


class DependencyLocalityRule(Wattleflow, IStrategy):
    """NFR-ORG-01 — shared helpers must be acyclic and broadly used (fan-in ≥ 2)."""

    def execute(self, caller: IWattleflow, *, src, reg, source, **kwargs) -> list[Finding]:
        shared = reg["shared_namespace"]
        builder = ImportGraphBuilder(src, reg)
        for path in source.create_iterator():
            builder.add(path)
        fanin = builder.build()

        findings = builder.violations()
        # Criterion 1: every shared helper module has fan-in >= 2 distinct domains.
        fanin_severity = Criterion.severity(reg, "helper_fan_in", WARNING)
        for helper, doms in sorted(fanin.items()):
            consumers = doms - {shared}
            if len(consumers) >= 2:
                continue
            who = ", ".join(sorted(consumers)) or "none"
            findings.append(
                Finding(
                    "ORG-01",
                    fanin_severity,
                    src / shared / f"{helper}.py",
                    0,
                    f"helpers.{helper}",
                    f"shared helper used by {len(consumers)} domain(s) [{who}] — criterion 1 "
                    "wants >=2 (tolerated; relocate or keep domain-local)",
                    kind="single-consumer-helper",
                    detail=f"used only by: {who}",
                )
            )
        return findings


# --------------------------------------------------------------------------- #
# endregion NFR-ORG-01 — Dependency Locality                                  #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region NFR-ORG-03 — TypeVar Nomenclature                                    #
# --------------------------------------------------------------------------- #
class TypeVarRule(Wattleflow, IStrategy):
    """NFR-ORG-03 — a TypeVar name must name a semantic role, not a mechanism."""

    def execute(self, caller: IWattleflow, *, src, reg, source, **kwargs) -> list[Finding]:
        cfg = reg.get("type_vars", {})
        roles = set(cfg.get("roles", []))
        synonyms = cfg.get("synonyms", {})
        tolerated = set(cfg.get("tolerated", []))
        acronyms = reg.get("acronyms", [])
        # Acronym casing is enforced at whatever level the registry declares —
        # WARNING while the decision is open, ERROR once it is taken.
        casing = (Criterion.acronym_severity(reg), reg.get("acronym_pending", "an open DR"))
        # Every ORG-03 verdict is the same declared check, so it carries the
        # severity the registry gives that check (POLICY §9) — not a constant here.
        role_sev = Criterion.severity(reg, "typevar_role_vocabulary", ERROR)
        findings: list[Finding] = []
        for path in source.create_iterator():
            self._check_file(path, roles, synonyms, tolerated, acronyms, casing, role_sev, findings)
        return findings

    def _check_file(self, path, roles, synonyms, tolerated, acronyms, casing, role_sev, findings):
        tree = SourceFile.of(path).tree
        if tree is None:
            return

        def add(sev, line, name, msg, kind="typevar-role"):
            findings.append(Finding("ORG-03", sev, path, line, name, msg, kind=kind))

        single_letters: set[str] = set()
        for node in ast.walk(tree):
            tv = self._typevar_assign(node)
            if tv is None:
                continue
            name, call = tv
            self._check_name(
                name,
                call,
                roles,
                synonyms,
                tolerated,
                acronyms,
                casing,
                role_sev,
                node.lineno,
                add,
            )
            if len(name) == 1 and name.isalpha() and not self._is_constrained(call):
                single_letters.add(name)

        self._check_generic_arity(tree, single_letters, role_sev, add)

    def _check_name(
        self, name, call, roles, synonyms, tolerated, acronyms, casing, role_sev, line, add
    ):
        # 5) variance must not be encoded in the name — use covariant=/contravariant=.
        if name.endswith(("_co", "_contra")):
            add(
                role_sev,
                line,
                name,
                "variance encoded in name — declare it via TypeVar() args (criterion 5)",
            )
            return
        # branded name pending a DR decision (rename to canonical role vs keep) → WARN.
        if name in tolerated:
            add(
                WARNING,
                line,
                name,
                "branded TypeVar — ADR must decide rename to canonical role vs keep (criterion 1)",
            )
            return
        # 2/3) bare single-letter is allowed ONLY for one unconstrained parameter.
        if len(name) == 1 and name.isalpha():
            if self._is_constrained(call):
                add(
                    role_sev,
                    line,
                    name,
                    "single-letter name on a bounded/constrained TypeVar carries a role — "
                    "name it from the role vocabulary (criterion 3)",
                )
            return
        # 2) mechanism suffix carries zero discriminating information.
        suffix = self._mechanism_suffix(name)
        if suffix:
            add(
                role_sev,
                line,
                name,
                f"mechanism suffix '{suffix}' carries no information — drop it (criterion 2)",
            )
            return
        # 6) synonym of a canonical role.
        canon = synonyms.get(name)
        if canon:
            add(role_sev, line, name, f"synonym of canonical role '{canon}' — rename (criterion 6)")
            return
        # 4) acronym casing follows PEP 8 (all-caps).
        for tok in Naming.tokenize(name):
            cf = Naming.casefold_lookup(tok, acronyms)
            if cf and cf != tok:
                severity, pending = casing
                note = (
                    "criterion 4"
                    if severity == ERROR
                    else f"undecided ({pending} pending); waiver declared, not enforced"
                )
                add(
                    severity,
                    line,
                    name,
                    f"acronym '{tok}' casing differs from '{cf}' — {note}",
                    kind="acronym-case",
                )
        # 1) must resolve to the registered role vocabulary.
        if name not in roles:
            add(
                role_sev,
                line,
                name,
                "not in the registered role vocabulary (extend via ADR, criterion 1)",
            )

    @staticmethod
    def _typevar_assign(node) -> tuple[str, ast.Call] | None:
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            return None
        func = node.value.func
        callee = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        if callee != "TypeVar":
            return None
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            return None
        return node.targets[0].id, node.value

    @staticmethod
    def _is_constrained(call: ast.Call) -> bool:
        # bound=... or constraints (TypeVar("X", int, str)) → carries a role.
        has_bound = any(k.arg == "bound" for k in call.keywords)
        return has_bound or len(call.args) > 1

    @staticmethod
    def _mechanism_suffix(name: str) -> str | None:
        if name != "Type" and name.endswith("Type"):
            return "Type"
        if name.endswith("_t"):
            return "_t"
        # trailing capital T on a multi-char mixed-case name (YieldT, SendT), but
        # never on an all-caps acronym (e.g. a hypothetical RDFT stays an acronym).
        if len(name) > 1 and name.endswith("T") and not name.isupper():
            return "T"
        return None

    @staticmethod
    def _check_generic_arity(tree, single_letters: set[str], role_sev: int, add) -> None:
        # 3) two or more single-letter parameters in one Generic[...] is a violation.
        for node in ast.walk(tree):
            if not isinstance(node, ast.Subscript):
                continue
            value = node.value
            base = value.id if isinstance(value, ast.Name) else getattr(value, "attr", None)
            if base not in ("Generic", "Protocol"):
                continue
            elts = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
            params = {e.id for e in elts if isinstance(e, ast.Name) and e.id in single_letters}
            if len(params) >= 2:
                add(
                    role_sev,
                    node.lineno,
                    ",".join(sorted(params)),
                    "two or more single-letter type parameters in one Generic[...] — "
                    "give each a distinct role noun (criterion 3)",
                )


# --------------------------------------------------------------------------- #
# endregion NFR-ORG-03 — TypeVar Nomenclature                                 #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region NFR-ORG-07 — Preset whitelist declaration                            #
# --------------------------------------------------------------------------- #
class PresetAllowedRule(Wattleflow, IStrategy):
    """NFR-ORG-07 — the preset whitelist is a class attribute named `ALLOWED`.

    Three criteria, one check, because they are three faces of one fact —
    PresetDecorator resolves the whitelist from ``type(parent).ALLOWED``:

    * §1 name — a synonym is never resolved, so the whitelist reads empty and
      every configured key is dropped without a word.
    * §2 scope — a module-level constant is equally invisible; it survives only
      while some constructor hand-carries it, and no subclass can extend it.
    * §3 forwarding — a class that declares ALLOWED and still passes `allowed=`
      upward keeps a second copy of the same fact, free to drift from the first.
    """

    def execute(self, caller: IWattleflow, *, src, reg, source, **kwargs) -> list[Finding]:
        cfg = reg.get("preset_allowed", {}) or {}
        canonical = cfg.get("declaration", "ALLOWED")
        synonyms = set(cfg.get("synonyms", []))
        severity = Criterion.severity(reg, "preset_allowed_declaration", ERROR)
        forwarding_declared = str(cfg.get("forwarding", "")).lower() == "prohibited"

        findings: list[Finding] = []
        for path in source.create_iterator():
            self._check_file(path, canonical, synonyms, severity, forwarding_declared, findings)
        return findings

    def _check_file(self, path, canonical, synonyms, severity, forwarding, findings):
        tree = SourceFile.of(path).tree
        if tree is None:
            return

        def add(sev, line, name, msg, kind, detail=None):
            findings.append(Finding("ORG-07", sev, path, line, name, msg, kind=kind, detail=detail))

        # §2 — module scope. Both the canonical name and any synonym qualify:
        # the point is that no class owns the declaration.
        for node in tree.body:
            for target in self._assigned_names(node):
                name, line = target
                if name != canonical and name not in synonyms:
                    continue
                add(
                    severity,
                    line,
                    name,
                    f"`{name}` declared at module scope — PresetDecorator resolves the "
                    f"whitelist from `type(self).{canonical}`, so nothing here is found "
                    "once a constructor stops hand-carrying it (criterion 2)",
                    "preset-allowed-scope",
                    detail=f"module-level {name}",
                )

        for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
            declares_canonical = False
            for stmt in cls.body:
                for name, line in self._assigned_names(stmt):
                    if name == canonical:
                        declares_canonical = True
                    elif name in synonyms:
                        # §1 — a synonym is silently unresolvable.
                        add(
                            severity,
                            line,
                            f"{cls.name}.{name}",
                            f"preset whitelist named `{name}` — PresetDecorator only "
                            f"resolves `{canonical}`, so this class permits nothing and "
                            "every configured key is dropped silently (criterion 1)",
                            "preset-allowed-name",
                            detail=f"{cls.name}.{name} → rename to {canonical}",
                        )
            # §3 — declared AND forwarded is one fact stored twice.
            if declares_canonical and forwarding:
                for line in self._forwarded_allowed(cls):
                    add(
                        WARNING,
                        line,
                        f"{cls.name}.{canonical}",
                        f"`{canonical}` is declared on the class and still forwarded as "
                        "`allowed=` — the base resolves it, so the argument is a second "
                        "copy free to drift (criterion 3)",
                        "preset-allowed-forwarded",
                        detail=f"{cls.name} forwards allowed=",
                    )

    @staticmethod
    def _assigned_names(node) -> list[tuple[str, int]]:
        """(name, line) for every plain or annotated assignment target."""
        if isinstance(node, ast.Assign):
            return [(t.id, node.lineno) for t in node.targets if isinstance(t, ast.Name)]
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            return [(node.target.id, node.lineno)]
        return []

    @staticmethod
    def _forwarded_allowed(cls: ast.ClassDef) -> list[int]:
        """Lines where this class forwards `allowed=` to a constructor.

        Restricted to `__init__` calls (`super().__init__`, `Base.__init__`):
        criterion 3 is about forwarding the whitelist UP the chain, and matching
        any call at all flagged unrelated helpers that happen to take `allowed=`.
        """
        out: list[int] = []
        for node in ast.walk(cls):
            if not isinstance(node, ast.Call):
                continue
            if getattr(node.func, "attr", None) != "__init__":
                continue
            for kw in node.keywords:
                if kw.arg == "allowed":
                    out.append(node.lineno)
        return out


# --------------------------------------------------------------------------- #
# endregion NFR-ORG-07 — Preset whitelist declaration                         #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region NFR-SEC-03 — Supply chain & distribution manifest                    #
# --------------------------------------------------------------------------- #
class SupplyChainRule(Wattleflow, IStrategy):
    """NFR-SEC-03 — the tier a module imports from, and the manifest that ships it.

    Two checks, one requirement:

    * `clean_core_imports` (criterion 1) — a module's home distribution is fixed
      by its import closure. The tool already computed that fact, but spent it
      only on EXCLUDING the module from the ORG rules; NFR-SEC-03's implementation
      note says the same edge must be *reported*, because a shared third-party
      dependency correlates breaches across every module that carries it (log4j).
      A silent exclusion turns 47% of a tree into a green vector.
    * `distribution_manifest` (criteria 2/3) — the packaging manifest is a claim
      about ownership. Two ways it lies without anyone noticing: a `packages.find`
      section without `namespaces` finds nothing at all in a PEP 420 tree, and an
      `exclude` glob written for a foreign subtree can take an owned one with it,
      leaving a wheel that imports what it does not ship.

    Both are claims about a *manifest*, not about an artefact. Proof lives in the
    built wheel's RECORD (criterion 5); these findings say where to look.
    """

    def execute(self, caller: IWattleflow, *, src, reg, source, **kwargs) -> list[Finding]:
        return self._tier(caller, src, reg) + self._manifest(caller, src, reg)

    # region tier
    @staticmethod
    def _tier(caller, src: Path, reg: dict) -> list[Finding]:
        severity = Criterion.severity(reg, "clean_core_imports", ERROR)
        scope = reg.get("scope") or {}
        waivers = {
            str(entry.get("module")): entry
            for entry in (scope.get("guarded_optional") or ())
            if entry.get("module")
        }
        out: list[Finding] = []
        # The whole tree, not `caller.excluded`: a waived module is in scope for the
        # ORG rules (DR-WFL-003) and therefore absent from that set, but its waiver
        # must stay visible for as long as it is in force (D-11) — reading only the
        # excluded set would have silenced exactly the record it depends on.
        for path in caller.all_files():
            foreign = sorted(SourceFile.of(path).foreign_roots(caller.core_libs))
            if not foreign:
                continue  # nothing outside the tier — no supply-chain fact to report
            rel = path.relative_to(src).as_posix()
            waiver = waivers.get(rel)
            if waiver is not None:
                declared = set(waiver.get("packages") or ())
                beyond = [pkg for pkg in foreign if pkg not in declared]
                if not beyond:
                    # A waiver stays VISIBLE for as long as it is in force (D-11):
                    # its silent disappearance has to be a finding, which it cannot
                    # be if the waived state was never reported.
                    out.append(
                        Finding(
                            "SEC-03",
                            INFO,
                            path,
                            0,
                            rel,
                            f"guarded optional dependency ({', '.join(foreign)}) — waived by "
                            f"{waiver.get('dr', 'an undeclared DR')}, fallback "
                            f"{waiver.get('fallback', 'undeclared')}; the waiver holds only "
                            "while the masking test passes",
                            kind="foreign-import",
                            detail=f"waived ({waiver.get('dr', 'no DR')}): {', '.join(foreign)}",
                        )
                    )
                    continue
                foreign = beyond
            out.append(
                Finding(
                    "SEC-03",
                    severity,
                    path,
                    0,
                    rel,
                    f"imports {', '.join(foreign)} — outside the tier this distribution "
                    "declares (criterion 1); its home distribution is the one that owns "
                    "the dependency",
                    kind="foreign-import",
                    detail=f"imports {', '.join(foreign)}",
                )
            )
        return out

    # endregion tier

    # region manifest
    @classmethod
    def _manifest(cls, caller, src: Path, reg: dict) -> list[Finding]:
        cfg = reg.get("distribution_manifest") or {}
        declared = cfg.get("pyproject")
        if not declared:
            return []
        pyproject = caller.home / declared
        severity = Criterion.severity(reg, "distribution_manifest", WARNING)
        if not pyproject.is_file():
            return [
                Finding(
                    "SEC-03",
                    INFO,
                    caller.home,
                    0,
                    declared,
                    "the criterion names a packaging manifest that does not exist at "
                    "this path — manifest checks could not run",
                    kind="declared-blind-spot",
                    detail=f"missing manifest: {declared}",
                )
            ]
        try:
            with pyproject.open("rb") as handle:
                data = tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError) as e:
            return [
                Finding(
                    "SEC-03",
                    INFO,
                    pyproject,
                    0,
                    declared,
                    f"packaging manifest unreadable ({e}) — manifest checks could not run",
                    kind="declared-blind-spot",
                    detail=f"unreadable manifest: {declared}",
                )
            ]

        find = ((data.get("tool") or {}).get("setuptools") or {}).get("packages") or {}
        find = find.get("find") if isinstance(find, dict) else None
        if not isinstance(find, dict):
            return []  # implicit discovery — nothing declared here to contradict the tree

        out: list[Finding] = []
        if not find.get("namespaces") and not (src / "__init__.py").is_file():
            out.append(
                Finding(
                    "SEC-03",
                    severity,
                    pyproject,
                    0,
                    "[tool.setuptools.packages.find]",
                    f"`{src.name}` is a PEP 420 namespace (no __init__.py) but the manifest "
                    "does not set `namespaces = true` — setuptools' finder returns no "
                    "packages, so the built wheel ships nothing (criterion 3)",
                    kind="manifest-no-namespaces",
                    detail="packages.find without `namespaces = true` over a PEP 420 tree",
                )
            )
        globs = find.get("exclude") or []
        out += cls._excluded_but_imported(caller, src, globs, severity, pyproject)
        return out

    @staticmethod
    def _excluded_but_imported(caller, src: Path, globs, severity: int, pyproject: Path):
        # Packages present in the tree, keyed by dotted name → directory.
        packages: dict[str, Path] = {}
        for path in caller.all_files():
            rel = path.relative_to(src).parent
            packages.setdefault(".".join((src.name,) + rel.parts), src / rel)

        matched = {name for name in packages if any(fnmatch.fnmatch(name, glob) for glob in globs)}
        # Report the outermost excluded package only; its sub-packages add no fact.
        outermost = {
            name
            for name in matched
            if not any(other != name and name.startswith(other + ".") for other in matched)
        }

        # Who imports into those packages, from outside them?
        out = []
        for name in sorted(outermost):
            directory = packages[name]
            importers = sorted(
                {
                    path
                    for path in caller.all_files()
                    if not path.is_relative_to(directory)
                    for module in SourceFile.of(path).imported_modules()
                    if module == name or module.startswith(name + ".")
                }
            )
            if not importers:
                continue  # excluded and unused here — the glob is doing its job
            sample = ", ".join(p.relative_to(src).as_posix() for p in importers[:3])
            more = f" (+{len(importers) - 3} more)" if len(importers) > 3 else ""
            out.append(
                Finding(
                    "SEC-03",
                    severity,
                    pyproject,
                    0,
                    name,
                    f"the manifest excludes `{name}` from packaging, yet {len(importers)} "
                    f"module(s) of this distribution import it — a wheel that imports what "
                    f"it does not ship (criterion 2). Importers: {sample}{more}",
                    kind="manifest-excluded-package",
                    detail=f"{name} excluded but imported by {len(importers)} module(s)",
                )
            )
        return out

    # endregion manifest


# --------------------------------------------------------------------------- #
# endregion NFR-SEC-03 — Supply chain & distribution manifest                 #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Linter — Strategy context (IStrategyContext)                         #
# --------------------------------------------------------------------------- #
class WemLint(Wattleflow, IStrategyContext):
    """Runs each NFR rule (an IStrategy) over the shared source tree."""

    def __init__(self, src: Path, reg: dict, home: Path | None = None):
        super().__init__()
        self._src = src
        self._reg = reg
        # Root of the distribution under measurement (the parent of its tools/),
        # so a rule can reach its packaging manifest without guessing.
        self._home = home if home is not None else src.parent
        scope = reg.get("scope", {})
        # Local names (own domains + shared namespace) are intra-project even when
        # imported bare (a malformed `from concrete import …`), never third-party.
        local = set(reg.get("domains", [])) | {reg.get("shared_namespace", "")}
        self._core_libs = frozenset(set(scope.get("core_libraries", [])) | local)
        self._files = tuple(p for p in sorted(src.rglob("*.py")) if "__pycache__" not in p.parts)
        self.waived = self._waived_modules(src, scope, self._files)
        self.excluded = self._out_of_scope(src, scope, self._core_libs, self._files, self.waived)
        self._source = SourceTree(src, self.excluded)
        self._strategy: IStrategy | None = None

    @property
    def core_libs(self) -> frozenset[str]:
        return self._core_libs

    @property
    def home(self) -> Path:
        return self._home

    def all_files(self) -> tuple[Path, ...]:
        """Every module in the tree — including the ones the ORG rules skip.

        The scope filter is a decision about which rules apply, never about which
        files exist; a supply-chain or manifest check must see the whole tree.
        """
        return self._files

    def present_domains(self) -> set[str]:
        domains, shared = set(self._reg.get("domains", [])), self._reg.get("shared_namespace", "")
        return {
            d for d in (Naming.file_domain(p, self._src, domains, shared) for p in self._files) if d
        }

    @staticmethod
    def _waived_modules(src: Path, scope: dict, files) -> frozenset[Path]:
        # DR-WFL-003: a guarded reference whose fallback is functionally complete
        # does NOT displace the module from the tier. SEC-03 read that waiver, the
        # scope filter did not, so the ORG rules skipped three in-tier modules
        # while the same run printed "waived by DR-WFL-003" about them.
        declared = {
            str(entry.get("module"))
            for entry in (scope.get("guarded_optional") or ())
            if entry.get("module")
        }
        return frozenset(p for p in files if p.relative_to(src).as_posix() in declared)

    @staticmethod
    def _out_of_scope(
        src: Path, scope: dict, core_libs: frozenset[str], files, waived: frozenset[Path]
    ) -> frozenset[Path]:
        globs = scope.get("exclude_paths", [])
        excluded: set[Path] = set()
        for path in files:
            if path in waived:
                continue
            rel = path.relative_to(src).as_posix()
            if any(fnmatch.fnmatch(rel, g) for g in globs) or Naming.foreign_imports(
                path, core_libs
            ):
                excluded.add(path)
        return frozenset(excluded)

    def unparsable(self) -> list[Finding]:
        """Modules that could not be parsed — a measurement that did not happen.

        Every rule reads the same AST, so a file that does not parse is skipped
        by all of them; SEC-03 additionally saw an empty import list and read it
        as "imports nothing foreign", i.e. as in-tier. Raised here, once per run
        and outside any rule, so no `--select` can make the gap invisible.
        """
        out: list[Finding] = []
        for path in self._files:
            error = SourceFile.of(path).error
            if error is None:
                continue
            out.append(
                Finding(
                    "EXC",
                    ERROR,
                    path,
                    error.lineno or 0,
                    str(path.relative_to(self._src)),
                    f"cannot be parsed ({error.msg}) — every rule skipped it and no "
                    "verdict about it is available; unmeasured must not read as clean",
                    kind="unparsable-module",
                    detail=f"syntax error line {error.lineno or '?'}: {error.msg}",
                )
            )
        return out

    def blind_spots(self) -> list[Finding]:
        """Declared unmeasured territory — dictionary.yaml: `slijepa-pjega`.

        A blind spot is declared, never silenced. Two sources feed this:
        modules the clean-core scope filter dropped (they import third-party, so
        they belong to another distribution), and the registry's own
        `blind_spots` list. Both surface in the vector as INFO, so a reader can
        never mistake "not measured" for "measured clean".
        """
        out: list[Finding] = []
        for path in sorted(self.excluded):
            foreign = ", ".join(sorted(Naming.foreign_imports(path, self._core_libs)))
            # Only the tier reason is echoed by SEC-03; a path dropped by an
            # exclude_paths glob raises nothing there, and claiming otherwise made
            # this message assert a second record that was never written.
            reason = f"imports {foreign}" if foreign else "matched an exclude_paths glob"
            echo = (
                "the same fact is raised as a SEC-03 finding, so the skip is recorded "
                "twice on purpose and silenced nowhere"
                if foreign
                else "the criterion itself put this path out of scope, so this INFO is "
                "the only record of the skip"
            )
            out.append(
                Finding(
                    "EXC",
                    INFO,
                    path,
                    0,
                    str(path.relative_to(self._src)),
                    f"outside the declared tier ({reason}) — the ORG rules skipped this "
                    f"module; {echo}",
                    kind="out-of-scope-module",
                    detail=reason,
                )
            )
        for note in self._reg.get("blind_spots") or []:
            out.append(
                Finding(
                    "EXC",
                    INFO,
                    self._src,
                    0,
                    "(registry)",
                    f"declared blind spot: {note}",
                    kind="declared-blind-spot",
                    detail=str(note),
                )
            )
        return out

    def set_strategy(self, strategy: IStrategy) -> None:
        self._strategy = strategy

    def execute_strategy(self, caller: IWattleflow, **kwargs) -> list[Finding]:
        # `caller` is part of the IStrategyContext contract since core v0.0.0.46;
        # it is forwarded verbatim so a rule can attribute its findings.
        return self._strategy.execute(
            caller, src=self._src, reg=self._reg, source=self._source, **kwargs
        )

    def run(self, rules) -> list[Finding]:
        findings: list[Finding] = []
        for rule in rules:
            self.set_strategy(rule)
            findings += self.execute_strategy(self)
        return findings

    def import_graph(self) -> ImportGraphBuilder:
        # Fresh ORG-01 graph over the same in-scope tree, for the --graph view.
        builder = ImportGraphBuilder(self._src, self._reg)
        for path in self._source.create_iterator():
            builder.add(path)
        return builder


# --------------------------------------------------------------------------- #
# endregion Linter — Strategy context (IStrategyContext)                      #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Rule factory (IFactory)                                              #
# --------------------------------------------------------------------------- #
class RuleFactory(Wattleflow, IFactory):
    """Creates the NFR check strategy for a registry id (e.g. 'ORG-02')."""

    _RULES: dict[str, type[IStrategy]] = {
        "ORG-01": DependencyLocalityRule,
        "ORG-02": NomenclatureRule,
        "ORG-03": TypeVarRule,
        "ORG-07": PresetAllowedRule,
        "SEC-03": SupplyChainRule,
    }

    @staticmethod
    def create(**kwargs) -> IStrategy:
        nfr = kwargs["nfr"]
        try:
            return RuleFactory._RULES[nfr]()
        except KeyError:
            known = ", ".join(RuleFactory._RULES)
            raise ValueError(f"unknown NFR rule '{nfr}' (known: {known})") from None

    @staticmethod
    def available() -> tuple[str, ...]:
        return tuple(RuleFactory._RULES)


# --------------------------------------------------------------------------- #
# endregion Rule factory (IFactory)                                           #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Application                                                          #
# --------------------------------------------------------------------------- #
class Locale:
    """Report strings, read from the criterion registry (`MESSAGES`).

    The tool holds no message text: a language is added by editing the
    registry, not this file. `en` is the default and the fallback, so a
    missing translation degrades to UK English instead of printing a key.
    """

    DEFAULT = "en"
    _MESSAGES: dict[str, dict[str, str]] = {}
    _CATALOGUE: dict[str, dict] = {}

    @classmethod
    def install(cls, reg: dict) -> None:
        cls._MESSAGES = reg.get("MESSAGES") or {}
        cls._CATALOGUE = reg.get("CATALOGUE") or {}

    @classmethod
    def kinds(cls) -> frozenset[str]:
        return frozenset(cls._CATALOGUE)

    @classmethod
    def entry(cls, kind: str, lang: str) -> dict:
        """Catalogue entry flattened for one language; `en` fills any gap."""
        e = cls._CATALOGUE.get(kind, {})
        base = e.get(cls.DEFAULT, {})
        entry = {"code": e.get("code", "?"), "ref": e.get("ref", "")} | base | e.get(lang, {})
        # A half-written catalogue entry must degrade, never crash a run: the
        # report is presentation, and presentation cannot decide a verdict (D-13).
        entry.setdefault("title", kind)
        entry.setdefault("why", [])
        entry.setdefault("fix", [])
        return entry

    @classmethod
    def available(cls) -> tuple[str, ...]:
        return tuple(cls._MESSAGES) or (cls.DEFAULT,)

    @classmethod
    def resolve(cls, reg: dict, override: str | None) -> str:
        lang = override or reg.get("report_language") or cls.DEFAULT
        return lang if lang in cls._MESSAGES else cls.DEFAULT

    @classmethod
    def text(cls, lang: str, key: str, **fmt) -> str:
        table = cls._MESSAGES
        msg = table.get(lang, {}).get(key) or table.get(cls.DEFAULT, {}).get(key)
        if msg is None:
            # Registry is incomplete: surface the key rather than crash the run.
            return f"<{key}>"
        return msg.format(**fmt) if fmt else msg


class Application:
    """CLI wrapper around the lint: builds the parser and runs the selected rules."""

    # Graph-rendering config (worst-first severity drives edge colour + composite label).
    _TAG_SEVERITY = {"CYCLE": 3, "LAYERING": 2, "LEAF": 1}
    _TAG_COLOUR = {"CYCLE": "\033[31m", "LAYERING": "\033[33m", "LEAF": "\033[34m"}
    _DIM, _RESET = "\033[2m", "\033[0m"

    def __init__(self, argv: list[str] | None = None):
        self.argv = argv
        # Populate the format→renderer registry before the parser (choices) and
        # _render_graph (dispatch) read it.
        self._graph_renderers = self._register_graph_renderers()

    def run(self) -> int:
        parser = self._build_parser()
        args = parser.parse_args(self.argv)
        return self._lint(args)

    def _build_parser(self) -> argparse.ArgumentParser:
        # The INVOCATION directory, never the resolved one: a distribution may
        # symlink this tool, and the tree it wants measured is its own (N-01).
        here = _CALL_HOME
        ap = argparse.ArgumentParser(
            description="Wattleflow NFR lint (" + ", ".join(RuleFactory.available()) + ")"
        )
        ap.add_argument("--version", action="version", version=f"wem_lint {__version__}")
        ap.add_argument(
            "--lang",
            default=None,
            help="report language; choices come from the registry `MESSAGES` table, "
            "defaulting to its `report_language`",
        )
        ap.add_argument("--src", type=Path, default=here.parent / "src" / "wattleflow")
        ap.add_argument(
            "--registry",
            type=Path,
            default=here / "dictionary.json",
            help="criterion dictionary: the code vocabulary in JSON "
            "(cut from the `code:` block of documentation/dictionary.yaml)",
        )
        ap.add_argument(
            "--messages",
            type=Path,
            default=_TOOL_HOME / "messages.json",
            help="presentation file (report strings + finding catalogue), shared by "
            "every distribution and versioned apart from the criterion; a criterion "
            "carrying inline MESSAGES/CATALOGUE overrides it",
        )
        ap.add_argument("--quiet", action="store_true", help="suppress INFO findings")
        ap.add_argument(
            "--format",
            choices=("friendly", "compact"),
            default="friendly",
            help="report style: friendly (explanation once per rule) or compact one-liners",
        )
        ap.add_argument(
            "--select",
            default=",".join(RuleFactory.available()),
            help="comma-separated NFR ids to run (default: all)",
        )
        ap.add_argument(
            "--graph",
            choices=tuple(self._graph_renderers),
            default="ascii",
            help="render the ORG-01 dependency graph in the given format (default: ascii)",
        )
        ap.add_argument(
            "--no-graph",
            dest="graph",
            action="store_const",
            const=None,
            help="suppress the dependency graph",
        )
        ap.add_argument(
            "--graph-out",
            type=Path,
            help="write the graph to a file (plain text, no colour) instead of stdout",
        )
        ap.add_argument("--no-color", action="store_true", help="disable ANSI colour in the graph")
        ap.add_argument(
            "--snapshot",
            type=Path,
            help="write the vector as JSON (a C-snapshot when the run is green); "
            "canonical location: documentation/workflow/conformance/",
        )
        ap.add_argument(
            "--date",
            default=date.today().isoformat(),
            help="date stamped into the snapshot (default: today)",
        )
        return ap

    def _lint(self, args) -> int:
        if not args.src.exists():
            print(f"wem_lint: source tree not found: {args.src}", file=sys.stderr)
            return 2
        if not any(p for p in args.src.rglob("*.py") if "__pycache__" not in p.parts):
            # A 0/0/0 run reads as "all clean"; almost always it is a mis-pointed --src.
            print(
                f"wem_lint: no .py files under {args.src} — nothing analysed (check --src)",
                file=sys.stderr,
            )
            return 2
        try:
            reg = self._load_registry(args.registry)
            self._load_presentation(reg, args.messages)
        except (OSError, json.JSONDecodeError, KeyError) as e:
            print(f"wem_lint: cannot read criterion {args.registry}: {e}", file=sys.stderr)
            return 2

        Locale.install(reg)
        if args.lang and args.lang not in Locale.available():
            print(
                f"wem_lint: unknown --lang {args.lang!r}; the registry declares "
                f"{', '.join(Locale.available())}",
                file=sys.stderr,
            )
            return 2
        args.lang = Locale.resolve(reg, args.lang)
        # Deduplicated: the vector is a count on a nominal scale, so a repeated id
        # in --select silently multiplied every finding the rule raised.
        selected = list(dict.fromkeys(s.strip() for s in args.select.split(",") if s.strip()))
        if not selected:
            # Same reason as the empty-tree guard above: no rule ran, so "0 errors"
            # is a statement about nothing.
            print(
                "wem_lint: --select resolved to no rules — nothing was checked "
                f"(known: {', '.join(RuleFactory.available())})",
                file=sys.stderr,
            )
            return 2
        try:
            rules = [RuleFactory.create(nfr=nfr) for nfr in selected]
        except ValueError as e:
            print(f"wem_lint: {e}", file=sys.stderr)
            return 2
        args.rules_run = selected
        lint = WemLint(args.src, reg, home=self._home_for(args.src))
        self._warn_if_misrooted(args, reg, selected)
        findings = (
            lint.run(rules)
            + lint.unparsable()
            + lint.blind_spots()
            + Criterion.drift(reg, args.src)
            + Criterion.absent_domains(reg, args.src, lint.present_domains())
        )

        triple = self._triple(reg, args)
        # --quiet trims the detailed listing only. The vector and the snapshot keep
        # every INFO, because blind spots are declared, never silenced
        # (dictionary.yaml: slijepa-pjega) — a switch must not be able to turn
        # "not measured" into "measured clean".
        shown = [f for f in findings if f.severity != INFO] if args.quiet else findings
        rc = self._report(args, selected, shown, findings, triple)
        if args.snapshot:
            self._write_snapshot(args, selected, findings, triple)
        # The graph is an ORG-01 artefact; drawing it for a run that did not select
        # ORG-01 would show a view no rule of this run produced.
        if args.graph and "ORG-01" in selected:
            self._render_graph(args, lint)
        return rc

    @staticmethod
    def _home_for(src: Path) -> Path:
        """Root of the distribution being measured — derived from --src, not from
        the invocation directory.

        Pinning it to the invoked tools/ was right for the DEFAULTS and wrong for
        everything else: with --src pointed elsewhere the manifest checks read the
        invoking distribution's pyproject.toml and attributed the verdict to a tree
        it does not describe. When --src has no enclosing manifest the answer is
        `src.parent`, so the manifest check reports a blind spot instead of
        borrowing another distribution's answer.
        """
        here = src.absolute()
        for candidate in (here, *list(here.parents)[:3]):
            if (candidate / "pyproject.toml").is_file():
                return candidate
        return here.parent

    @staticmethod
    def _load_registry(path: Path) -> dict:
        """Read the code vocabulary from the criterion dictionary.

        The vocabularies are split by audience: `dictionary.yaml` governs the
        discourse (entries/acronyms, read by people), `dictionary.json` governs
        code identifiers (read by this lint). Only the latter is a criterion, so
        only it is loaded here — in JSON, because a quality gate must not depend
        on a third-party parser. Two keys are derived:

          acronyms  — from `identifier_acronyms`. Deliberately NOT the discourse
                      `acronyms` table: that one lists doctrine abbreviations
                      (DQI, NFR, PDSA) and checking class names against it would
                      be nonsense. The two sets are disjoint by construction.
          acronym_severity — driven by `acronym_identifier_casing.status`, so
                      the enforcement level is a registry fact under DR
                      governance rather than a constant in this file.
        """
        doc = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict) or not isinstance(doc.get("domains"), list):
            raise KeyError(
                "no `domains` list — expected a criterion dictionary.json "
                "(the code vocabulary of one distribution)"
            )
        # JSON carries no comments: underscore-prefixed keys are the dictionary's
        # prose and are dropped before the rules see it.
        reg = {k: v for k, v in doc.items() if not k.startswith("_")}
        # Normalised once, here: the rules subscript these two directly, and a
        # criterion missing `shared_namespace` used to abort the run with a
        # traceback instead of the guarded exit the caller can act on.
        reg.setdefault("shared_namespace", "")
        reg["acronyms"] = reg.get("identifier_acronyms", [])
        casing = reg.get("acronym_identifier_casing") or {}
        reg["acronym_pending"] = casing.get("decision_pending", "an open DR")
        reg["criterion_path"] = str(path)
        # The reproducibility triple names the criterion (the code vocabulary) and
        # the discourse revision it was cut from — versioned apart from each other.
        reg["registry_version"] = reg.get("criterion_version", "unversioned")
        reg["dictionary_version"] = reg.get("dictionary_version", "unversioned")
        return reg

    @staticmethod
    def _load_presentation(reg: dict, path: Path) -> None:
        """Merge the report surface into the criterion.

        Presentation is versioned apart and sits outside the D-10 triple, so it
        lives in one shared file instead of being copied into every distribution's
        criterion — a copy would drift, and a wording fix would then read as a
        criterion change. A criterion that still carries inline MESSAGES/CATALOGUE
        keeps them: the older single-file form stays valid.
        """
        inline = {key: reg.get(key) for key in ("MESSAGES", "CATALOGUE")}
        doc: dict = {}
        if not all(inline.values()):
            if not path.is_file():
                raise KeyError(
                    f"presentation file not found: {path} — the report strings live "
                    "outside the criterion since v1.11.0 (use --messages to point at it)"
                )
            doc = json.loads(path.read_text(encoding="utf-8"))
        for key in ("MESSAGES", "CATALOGUE"):
            table = inline[key] or doc.get(key) or {}
            complete = (
                table.get(Locale.DEFAULT)
                if key == "MESSAGES"
                else all(Locale.DEFAULT in v for v in table.values())
            )
            if not table or not complete:
                raise KeyError(
                    f"`{key}` missing or without an `{Locale.DEFAULT}` fallback — the "
                    "registry carries the report strings; the tool holds none"
                )
            reg[key] = table
        reg["presentation_version"] = (
            reg.get("presentation_version") or doc.get("presentation_version") or "unversioned"
        )
        # Named per source, not per run: a criterion carrying only one of the two
        # tables takes the other from the file, and recording a single path for
        # both would have the triple name a source that supplied half of it.
        sources = {key: "(inline)" if inline[key] else str(path) for key in inline}
        reg["presentation_path"] = (
            sources["MESSAGES"]
            if sources["MESSAGES"] == sources["CATALOGUE"]
            else f"MESSAGES={sources['MESSAGES']}, CATALOGUE={sources['CATALOGUE']}"
        )

    @staticmethod
    def _triple(reg: dict, args) -> dict[str, str]:
        # Reproducibility triple — dictionary.yaml: `trojka-reproducibilnosti`.
        # A finding without it is not reproducible, so it is printed with every
        # report and stored with every snapshot.
        return {
            "tool": f"wem_lint {__version__}",
            # Which rules actually ran. A partial --select used to print a vector
            # shaped exactly like a full run, so "0 errors" could mean "nothing
            # was asked" — coverage is declared, never inferred (D-11).
            "rules": ", ".join(args.rules_run),
            # The subject of the measurement. Without it the triple identifies the
            # instrument but not what it was pointed at — which is how a symlinked
            # tool reported another distribution's tree as green (N-01/N-02).
            "source": f"{args.src} [{reg.get('distribution', 'undeclared distribution')}]",
            # The criterion is the code vocabulary, versioned apart from the
            # discourse entries; both are named so a snapshot pins the exact file.
            "criterion": (
                f"{reg.get('criterion_path', 'dictionary.json')} "
                f"{reg.get('registry_version', 'unversioned')}"
                f" (dictionary.yaml {reg.get('dictionary_version', 'unversioned')})"
            ),
            "presentation": (
                f"{reg.get('presentation_path', '(inline)')} "
                f"{reg.get('presentation_version', 'unversioned')}"
            ),
            "platform": f"python {platform.python_version()} ({platform.system()})",
            # Not a triple member — presentation is versioned apart (D-13); carried
            # so a snapshot still records which wording produced it.
            "presentation_version": str(reg.get("presentation_version", "unversioned")),
            "python_reference": str(reg.get("python_reference", "unpinned")),
        }

    def _warn_if_misrooted(self, args, reg, selected) -> None:
        # ORG-01/ORG-02 are domain-scoped: a file's domain is its first path part under --src.
        # If no file maps to a declared domain/shared namespace, --src is not the package root
        # (e.g. it points at src/wattleflow/concrete), so those rules run inert — 0/0/0 is a
        # false "all clean". ORG-03 walks every file and is unaffected.
        if not ({"ORG-01", "ORG-02"} & set(selected)):
            return
        domains, shared = set(reg.get("domains", [])), reg.get("shared_namespace", "")
        files = (p for p in args.src.rglob("*.py") if "__pycache__" not in p.parts)
        if any(Naming.file_domain(p, args.src, domains, shared) for p in files):
            return
        print(
            f"wem_lint: WARNING — no file under {args.src} maps to a declared domain; "
            "ORG-01/ORG-02 are domain-scoped and had nothing to check. Point --src at the "
            "'wattleflow' package root (its children are the domains), not a sub-package.",
            file=sys.stderr,
        )

    def _render_graph(self, args, lint: WemLint) -> None:
        # Colour only when writing to an interactive terminal (never into a file),
        # honouring the NO_COLOR convention.
        color = (
            not args.no_color
            and not args.graph_out
            and sys.stdout.isatty()
            and "NO_COLOR" not in os.environ
        )
        text = self._graph_renderers[args.graph](
            lint.import_graph(), color=color, lang=getattr(args, "lang", Locale.DEFAULT)
        )
        if args.graph_out:
            args.graph_out.write_text(text + "\n", encoding="utf-8")
            print(f"\nwem_lint: graph written to {args.graph_out}")
        else:
            print(f"\n{text}")

    def _register_graph_renderers(self) -> dict:
        # Format→renderer registry. Add a format here + its bound method; the parser
        # exposes the keys as --graph choices, _render_graph dispatches on them.
        return {"ascii": self._render_ascii_graph}

    def _render_ascii_graph(
        self, builder: ImportGraphBuilder, color: bool = True, lang: str = Locale.DEFAULT
    ) -> str:
        """Render the package-level import DAG as a Unicode tree, tagging bad edges."""
        nodes, adj, viol, scope = builder.graph()

        def paint(text: str, code: str) -> str:
            return f"{code}{text}{self._RESET}" if color else text

        lines = [
            Locale.text(lang, "graph_title"),
            Locale.text(lang, "graph_hint"),
            "",
        ]
        for src in sorted(nodes):
            dsts = sorted(adj.get(src, ()))
            if not dsts:
                # In-scope & no outgoing = genuine leaf; out-of-scope = only ever a target.
                kind = Locale.text(lang, "graph_leaf" if src in scope else "graph_external")
                lines.append(f"{src}  {paint(f'({kind})', self._DIM)}")
                continue
            lines.append(src)
            for i, dst in enumerate(dsts):
                branch = "└─▶" if i == len(dsts) - 1 else "├─▶"
                v = viol.get((src, dst))
                if not v:
                    lines.append(f"  {branch} {dst}")
                    continue
                tags = sorted(v["tags"], key=lambda t: -self._TAG_SEVERITY[t])
                label = paint(f"{dst:<11} [{'+'.join(tags)}]", self._TAG_COLOUR[tags[0]])
                lines.append(f"  {branch} {label}  {paint('; '.join(v['notes']), self._DIM)}")
            lines.append("")

        tags = (("CYCLE", "tag_cycle"), ("LAYERING", "tag_layering"), ("LEAF", "tag_leaf"))
        legend = "  ".join(
            paint(f"{t} ({Locale.text(lang, k)})", self._TAG_COLOUR[t]) for t, k in tags
        )
        lines.append(Locale.text(lang, "legend") + legend)
        return "\n".join(lines)

    @staticmethod
    def _vector(findings) -> list[tuple[str, str, str, int]]:
        # Conformance vector: counts per (NFR, kind, severity). Counting is the only
        # operation a nominal scale admits — no weighted sum, no aggregate score
        # (METHODOLOGY §3b/§6.1; dictionary.yaml: `vektorski-nalaz`).
        counts: dict[tuple[str, str, str], int] = defaultdict(int)
        for f in findings:
            counts[(f.nfr, f.kind or "-", logging.getLevelName(f.severity))] += 1
        return [(nfr, kind, sev, n) for (nfr, kind, sev), n in sorted(counts.items())]

    def _report(self, args, selected, shown, findings, triple) -> int:
        # `shown` is what gets listed (possibly trimmed by --quiet); `findings` is
        # the complete set the vector and the counters are computed from.
        errors = sum(1 for f in findings if f.severity == ERROR)
        warns = sum(1 for f in findings if f.severity == WARNING)
        infos = sum(1 for f in findings if f.severity == INFO)

        if args.format == "compact":
            self._report_compact(args, selected, shown)
        else:
            self._report_friendly(args, shown)

        lang = args.lang
        print(f"\n== {Locale.text(lang, 'vector')} {'=' * 60}")
        rows = self._vector(findings)
        if not rows:
            print(f"  {Locale.text(lang, 'no_findings')}")
        for nfr, kind, sev, n in rows:
            print(f"  {nfr:<7} {kind:<24} {sev:<7} {n}")
        print(Locale.text(lang, "vector_note"))

        print(f"\n== {Locale.text(lang, 'reproducibility')} {'=' * 52}")
        for key in ("tool", "rules", "source", "criterion", "presentation", "platform"):
            print(f"  {key:<13} {triple[key]}")
        if not self._pin_matches(triple["python_reference"], platform.python_version()):
            print(
                Locale.text(
                    lang,
                    "python_pin",
                    pin=triple["python_reference"],
                    running=platform.python_version(),
                )
            )

        print(f"\n{'-' * 60}")
        print(Locale.text(lang, "summary", errors=errors, warns=warns, infos=infos))
        print(Locale.text(lang, "notes"))
        return 1 if errors else 0

    @staticmethod
    def _pin_matches(pin: str, running: str) -> bool:
        # Component-wise, not textual: `startswith` let a pin of "3.1" pass on
        # 3.11, 3.12 and 3.13 alike, so the warning stayed silent exactly where a
        # pin is worth having. An unpinned criterion has nothing to contradict.
        if not pin or pin == "unpinned":
            return True
        wanted = pin.split(".")
        return running.split(".")[: len(wanted)] == wanted

    def _write_snapshot(self, args, selected, findings, triple) -> None:
        """Write the run as a machine-readable vector.

        Only an all-green run is a C-snapshot (dictionary.yaml: `c-snimka` — an
        ARCHIVED GREEN vector). A run with errors is archived too, but labelled
        `finding-vector`, so the archive can never be mistaken for a conformance
        record it has not earned.
        """
        errors = sum(1 for f in findings if f.severity == ERROR)
        kind = "c-snapshot" if errors == 0 else "finding-vector"
        doc = {
            "kind": kind,
            "green": errors == 0,
            "date": args.date,
            "source": str(args.src),
            "rules_selected": selected,
            "reproducibility_triple": {
                k: triple[k] for k in ("tool", "source", "criterion", "platform")
            },
            # Outside the triple on purpose: the report surface cannot change a
            # verdict, so it must not make two snapshots look incomparable.
            "presentation": triple["presentation"],
            "presentation_version": triple["presentation_version"],
            "python_reference": triple["python_reference"],
            "vector": [
                {"nfr": nfr, "kind": k, "severity": sev, "count": n}
                for nfr, k, sev, n in self._vector(findings)
            ],
            # Only what is genuinely unmeasured territory. Registry drift and an
            # unparsable module are EXC too, but they are defects to act on — filing
            # them here would have dressed them as tolerated coverage gaps.
            "blind_spots": [
                {"module": f.name, "reason": f.detail}
                for f in findings
                if f.kind in ("out-of-scope-module", "declared-blind-spot")
            ],
            "findings": [
                {
                    "nfr": f.nfr,
                    "severity": logging.getLevelName(f.severity),
                    "kind": f.kind,
                    "location": self._location(f, args.src),
                    "name": f.name,
                    "message": f.message,
                }
                for f in findings
                if f.kind not in ("out-of-scope-module", "declared-blind-spot")
            ],
        }
        args.snapshot.parent.mkdir(parents=True, exist_ok=True)
        args.snapshot.write_text(
            json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"\nwem_lint: {kind} written to {args.snapshot}")

    def _report_compact(self, args, selected, findings) -> None:
        # Groups beyond the selected rules (EXC — blind spots) must still print, or
        # the declared-not-silenced requirement would hold only for the vector.
        extra = [n for n in dict.fromkeys(f.nfr for f in findings) if n not in selected]
        for nfr in list(selected) + extra:
            group = [f for f in findings if f.nfr == nfr]
            if not group:
                continue
            # EXC is a coverage dimension, not a requirement — labelling it NFR-EXC
            # would invent a requirement that does not exist in NFR.md.
            label = (
                f"NFR-{nfr}"
                if nfr in RuleFactory.available()
                else f"{nfr} ({Locale.text(args.lang, 'blind_spots_label')})"
            )
            print(f"\n=== {label} ===")
            # Highest logging level first (ERROR=40 > WARNING=30 > INFO=20).
            for f in sorted(group, key=lambda f: (-f.severity, str(f.path), f.line)):
                print(f.render(args.src))

    @staticmethod
    def _location(f: Finding, src: Path) -> str:
        try:
            rel = f.path.relative_to(src)
        except ValueError:
            rel = f.path
        return f"{rel}:{f.line}" if f.line else str(rel)

    def _report_friendly(self, args, findings) -> None:
        # Explanation printed ONCE per finding kind, instances listed compactly under
        # it — readable at any count. Kinds without a catalogue entry fall back to the
        # compact rendering, so nothing is ever swallowed.
        color = not args.no_color and sys.stdout.isatty() and "NO_COLOR" not in os.environ
        red, yellow, dim, reset = (
            ("\033[31m", "\033[33m", "\033[2m", "\033[0m") if color else ("", "", "", "")
        )

        # Grouped by (kind, severity), not by kind alone: one kind can be raised at
        # two levels (a grammar breach is an ERROR, a relaxed grouping package only
        # a WARNING), and a single badge over a mixed group would misreport the
        # milder half as the harsher one.
        groups: dict[tuple[str, int], list[Finding]] = {}
        rest: list[Finding] = []
        ordered = sorted(findings, key=lambda f: (-f.severity, f.kind or "", str(f.path), f.line))
        for f in ordered:
            if f.kind in Locale.kinds():
                groups.setdefault((f.kind, f.severity), []).append(f)
            else:
                rest.append(f)

        for (kind, sev), items in groups.items():
            c = Locale.entry(kind, args.lang)
            badge, col = (
                ("✖ ERROR", red)
                if sev >= ERROR
                else (("⚠ WARNING", yellow) if sev >= WARNING else ("ℹ INFO", ""))
            )
            print(f"\n{col}{badge} {c['code']} · {c['title']}{reset}  {dim}[{c['ref']}]{reset}\n")
            for ln in c["why"]:
                print(f"  {ln}")
            print()
            for ln in c["fix"]:
                print(f"  {ln}")
            print()
            width = max(len(self._location(f, args.src)) for f in items)
            for f in items:
                print(f"    {self._location(f, args.src):<{width}}  {f.detail or f.message}")

        if rest:
            print(f"\n{dim}{Locale.text(args.lang, 'other_findings')}{reset}")
            for f in rest:
                print(f.render(args.src))


if __name__ == "__main__":
    raise SystemExit(Application().run())
# --------------------------------------------------------------------------- #
# endregion Application                                                       #
# --------------------------------------------------------------------------- #
