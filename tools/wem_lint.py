# Module name: tools/wem_lint.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""wem_lint — static enforcement of the Wattleflow NFR registry.

Implements the machine-verifiable acceptance criteria of:
  * NFR-ORG-01 — Dependency Locality of Support Classes (import-graph checks)
  * NFR-ORG-02 — Class Nomenclature (name-grammar checks)
  * NFR-ORG-03 — TypeVar Nomenclature (generic-parameter role names)

The checks themselves are purely AST/import-graph based — no *measured* module is
imported, so a syntactically broken target still yields findings rather than a
crash. It is runnable on demand now and, once a CI pipeline exists, as a quality
gate. Runtime dependencies: none beyond the standard library and this
distribution's own `wattleflow.core` + `wattleflow.concrete` (see below). The
criterion is read from `tools/dictionary.json` — JSON, not YAML, so a quality
gate never depends on a third-party parser being installed.

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

from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Iterator

_STDLIB = set(sys.stdlib_module_names)

# The tool lives in <repo>/tools/ and consumes <repo>/src/wattleflow. Make the src
# layout importable before the framework imports below — a module-level side effect,
# legal here: tools are a consumer layer, not the interface layer.
_REPO_SRC = Path(__file__).resolve().parents[1] / "src"
if _REPO_SRC.is_dir() and str(_REPO_SRC) not in sys.path:
    sys.path.insert(0, str(_REPO_SRC))

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
__version__ = "1.5.0"

# Severity is a stdlib logging level (int); the report renders its level name.
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
    def foreign_imports(path: Path, core_libs: set[str]) -> set[str]:
        # Root packages imported from outside (stdlib ∪ wattleflow ∪ core_libs) —
        # the third-party libraries that place a module outside clean core.
        # ast.walk (not just tree.body) is deliberate: a lazy, in-function import
        # still fixes the module's home distribution (DR-WFL-002 §2.1), so it must
        # count here exactly like a module-level one.
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            return set()
        allowed = _STDLIB | {"wattleflow"} | core_libs
        foreign: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            else:
                continue
            for module in names:
                top = module.split(".")[0]
                if top and top not in allowed:
                    foreign.add(top)
        return foreign


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
    """NFR-ORG-02 — class-name grammar, scoped to the `pipelines` domain.

    KNOWN GAP: a registry without a `pipelines` domain (the clean-core workflow
    tree) makes this rule inert — including criterion 6, which NFR-ORG-02 scopes to
    *every* class, and which NFR-ORG-04/05 delegate here. Widening criterion 6 to
    all domains is a behaviour change, so it is a worklist item, not a silent fix.
    """

    def execute(self, caller: IWattleflow, *, src, reg, source, **kwargs) -> list[Finding]:
        findings: list[Finding] = []
        for path in source.create_iterator():
            self._check_file(path, src, reg, findings)
        return findings

    def _check_file(self, path, src, reg, findings):
        domain = Naming.file_domain(path, src, set(reg["domains"]), reg["shared_namespace"])
        if domain != "pipelines":
            return

        def add(sev, line, nm, msg):
            findings.append(Finding("ORG-02", sev, path, line, nm, msg))

        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as e:
            add(ERROR, e.lineno or 0, path.name, f"syntax error: {e}")
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
                    ERROR,
                    node.lineno,
                    node.name,
                    "`Pipeline` prefix on a non-pipeline class (criterion 2)",
                )
            if not is_pipeline:
                if node.name in reg.get("prohibited_standalone", []):
                    add(
                        ERROR,
                        node.lineno,
                        node.name,
                        "standalone generic role noun — must be domain-qualified (criterion 6)",
                    )
                continue
            if not has_prefix:
                add(
                    ERROR,
                    node.lineno,
                    node.name,
                    "pipeline class must carry the `Pipeline` prefix (criterion 2)",
                )
                continue
            if canon_pkg in reg.get("exempt_packages", []):
                add(
                    INFO,
                    node.lineno,
                    node.name,
                    f"package '{subpkg}' is exempt (deferred via ADR) — grammar not enforced",
                )
                continue
            if subpkg in reg.get("package_aliases", {}):
                add(
                    WARNING,
                    node.lineno,
                    node.name,
                    f"package '{subpkg}' should be renamed to canonical '{canon_pkg}' (decision 2)",
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
        # criterion, not a constant of the tool.
        casing_sev = reg.get("acronym_severity", WARNING)
        casing_pending = reg.get("acronym_pending", "an open DR")
        casing_note = (
            "criterion 4"
            if casing_sev == ERROR
            else f"undecided ({casing_pending} pending); waiver declared, not enforced"
        )

        def add(sev, msg):
            findings.append(Finding("ORG-02", sev, path, node.lineno, name, msg))

        # 1) Subject — longest leading run of segments that joins to a known subject.
        subject, used = None, 0
        for i in range(len(segs), 0, -1):
            if "".join(segs[:i]) in subjects:
                subject, used = "".join(segs[:i]), i
                break
        if subject is None:
            cf = Naming.casefold_lookup(segs[0], subjects) if segs else None
            if cf:
                add(casing_sev, f"subject '{segs[0]}' casing differs from '{cf}' — {casing_note}")
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
                add(casing_sev, f"acronym '{q}' casing differs from '{cf}' — {casing_note}")
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
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
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
        return [
            Finding(
                "ORG-01",
                ERROR,
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
        for helper, doms in sorted(fanin.items()):
            consumers = doms - {shared}
            if len(consumers) >= 2:
                continue
            who = ", ".join(sorted(consumers)) or "none"
            findings.append(
                Finding(
                    "ORG-01",
                    WARNING,
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
        casing = (reg.get("acronym_severity", WARNING), reg.get("acronym_pending", "an open DR"))
        findings: list[Finding] = []
        for path in source.create_iterator():
            self._check_file(path, roles, synonyms, tolerated, acronyms, casing, findings)
        return findings

    def _check_file(self, path, roles, synonyms, tolerated, acronyms, casing, findings):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            return

        def add(sev, line, name, msg):
            findings.append(Finding("ORG-03", sev, path, line, name, msg))

        single_letters: set[str] = set()
        for node in ast.walk(tree):
            tv = self._typevar_assign(node)
            if tv is None:
                continue
            name, call = tv
            self._check_name(
                name, call, roles, synonyms, tolerated, acronyms, casing, node.lineno, add
            )
            if len(name) == 1 and name.isalpha() and not self._is_constrained(call):
                single_letters.add(name)

        self._check_generic_arity(tree, single_letters, add)

    def _check_name(self, name, call, roles, synonyms, tolerated, acronyms, casing, line, add):
        # 5) variance must not be encoded in the name — use covariant=/contravariant=.
        if name.endswith(("_co", "_contra")):
            add(
                ERROR,
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
                    ERROR,
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
                ERROR,
                line,
                name,
                f"mechanism suffix '{suffix}' carries no information — drop it (criterion 2)",
            )
            return
        # 6) synonym of a canonical role.
        canon = synonyms.get(name)
        if canon:
            add(ERROR, line, name, f"synonym of canonical role '{canon}' — rename (criterion 6)")
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
                add(severity, line, name, f"acronym '{tok}' casing differs from '{cf}' — {note}")
        # 1) must resolve to the registered role vocabulary.
        if name not in roles:
            add(
                ERROR,
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
    def _check_generic_arity(tree, single_letters: set[str], add) -> None:
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
                    ERROR,
                    node.lineno,
                    ",".join(sorted(params)),
                    "two or more single-letter type parameters in one Generic[...] — "
                    "give each a distinct role noun (criterion 3)",
                )


# --------------------------------------------------------------------------- #
# endregion NFR-ORG-03 — TypeVar Nomenclature                                 #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Linter — Strategy context (IStrategyContext)                         #
# --------------------------------------------------------------------------- #
class WemLint(Wattleflow, IStrategyContext):
    """Runs each NFR rule (an IStrategy) over the shared source tree."""

    def __init__(self, src: Path, reg: dict):
        super().__init__()
        self._src = src
        self._reg = reg
        scope = reg.get("scope", {})
        # Local names (own domains + shared namespace) are intra-project even when
        # imported bare (a malformed `from concrete import …`), never third-party.
        local = set(reg.get("domains", [])) | {reg.get("shared_namespace", "")}
        self._core_libs = set(scope.get("core_libraries", [])) | local
        self.excluded = self._out_of_scope(src, scope, self._core_libs)
        self._source = SourceTree(src, self.excluded)
        self._strategy: IStrategy | None = None

    @staticmethod
    def _out_of_scope(src: Path, scope: dict, core_libs: set[str]) -> frozenset[Path]:
        globs = scope.get("exclude_paths", [])
        excluded: set[Path] = set()
        for path in src.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            rel = path.relative_to(src).as_posix()
            if any(fnmatch.fnmatch(rel, g) for g in globs) or Naming.foreign_imports(
                path, core_libs
            ):
                excluded.add(path)
        return frozenset(excluded)

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
            reason = f"imports {foreign}" if foreign else "matched an exclude_paths glob"
            out.append(
                Finding(
                    "EXC",
                    INFO,
                    path,
                    0,
                    str(path.relative_to(self._src)),
                    f"outside clean-core scope ({reason}) — no rule measured this module",
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
class Application:
    """CLI wrapper around the lint: builds the parser and runs the selected rules."""

    # Graph-rendering config (worst-first severity drives edge colour + composite label).
    _TAG_SEVERITY = {"CYCLE": 3, "LAYERING": 2, "LEAF": 1}
    _TAG_COLOUR = {"CYCLE": "\033[31m", "LAYERING": "\033[33m", "LEAF": "\033[34m"}
    _DIM, _RESET = "\033[2m", "\033[0m"

    # Friendly-report catalogue: one entry per finding kind. Anatomy: what happened
    # (title) → why it matters (why) → what to do (fix). Written for a junior reader
    # — no jargon in the message; the NFR reference is the door to the full rule.
    # The explanation prints ONCE per kind; instances list compactly below it.
    _CATALOGUE = {
        "import-cycle": {
            "code": "E1",
            "ref": "NFR-ORG-01 §3",
            "title": "import loop — two modules import each other",
            "why": (
                "Two modules import each other (directly or through a chain).",
                "That is a loop: Python cannot load them cleanly, and every change",
                "to one drags the other with it.",
            ),
            "fix": (
                "Fix: break the loop — move the shared piece somewhere both sides",
                "may import (a lower layer), so the arrows point one way only.",
            ),
        },
        "wrong-direction-import": {
            "code": "E2",
            "ref": "NFR-ORG-01 §3",
            "title": "foundation imports an upper layer (wrong direction)",
            "why": (
                "`helpers/` is the foundation of the building — everyone may use it.",
                "So it must not import from upper layers (`concrete/`, …), or the",
                "foundation ends up depending on a floor that stands on top of it:",
                "every change up there shakes the foundation, and in the worst case",
                "you get an import loop.",
            ),
            "fix": (
                "Fix: move the imported symbol down to a layer helpers may use,",
                "or use a stdlib replacement inside helpers.",
            ),
        },
        "misfiled-leaf": {
            "code": "E3",
            "ref": "NFR-ORG-01 §3",
            "title": "import target is foundation material, but labelled as a domain",
            "why": (
                "The imported package imports nothing from wattleflow itself — it is",
                "a pure leaf (foundation material). The registry, however, lists it",
                "as a domain (upper layer). The import is fine; the label is wrong.",
            ),
            "fix": (
                "Fix: update the registry — remove the package from `domains` so the",
                "tool treats it as foundation.",
            ),
        },
        "out-of-scope-module": {
            "code": "I1",
            "ref": "dictionary.yaml: slijepa-pjega",
            "title": "module not measured — outside clean-core scope",
            "why": (
                "This module imports a third-party library, so it belongs to another",
                "distribution (wattleflow-processors / examples) and every rule skipped",
                "it. Nothing here was checked — clean is not the same as unmeasured.",
                "Note: a real violation can hide behind this filter. helpers/config.py",
                "is skipped for `yaml`, yet it also imports concrete/ — an ORG-01 breach",
                "the instrument cannot see.",
            ),
            "fix": (
                "Not a defect to fix: a declared blind spot, listed so the vector never",
                "reads as full coverage. Measure it from the distribution that owns it.",
            ),
        },
        "declared-blind-spot": {
            "code": "I2",
            "ref": "dictionary.yaml: slijepa-pjega",
            "title": "registry declares this as unmeasured by construction",
            "why": (
                "The registry's `blind_spots` list names what the instrument cannot",
                "see by design (not by accident). Declaring it is the requirement;",
                "silence would be the defect.",
            ),
            "fix": ("Nothing to do — carried into every report and every snapshot.",),
        },
        "single-consumer-helper": {
            "code": "W1",
            "ref": "NFR-ORG-01 §1",
            "title": "shared helper used by only one package",
            "why": (
                "`helpers/` is the shared shelf: it should only hold things that at",
                "least TWO different packages use. A module with a single consumer",
                "belongs inside the package that uses it — closer to its user and",
                "easier to change.",
            ),
            "fix": (
                "Fix: move the module into its only consumer package, or leave it if",
                "a second consumer is coming soon.",
                "(Inherited from before — does not fail the build.)",
            ),
        },
    }

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
        here = Path(__file__).resolve().parent
        ap = argparse.ArgumentParser(description="Wattleflow NFR lint (ORG-01, ORG-02, ORG-03)")
        ap.add_argument("--version", action="version", version=f"wem_lint {__version__}")
        ap.add_argument("--src", type=Path, default=here.parent / "src" / "wattleflow")
        ap.add_argument(
            "--registry",
            type=Path,
            default=here / "dictionary.json",
            help="criterion dictionary: the code vocabulary in JSON "
            "(cut from the `code:` block of documentation/dictionary.yaml)",
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
        except (OSError, json.JSONDecodeError, KeyError) as e:
            print(f"wem_lint: cannot read registry {args.registry}: {e}", file=sys.stderr)
            return 2

        selected = [s.strip() for s in args.select.split(",") if s.strip()]
        try:
            rules = [RuleFactory.create(nfr=nfr) for nfr in selected]
        except ValueError as e:
            print(f"wem_lint: {e}", file=sys.stderr)
            return 2
        lint = WemLint(args.src, reg)
        self._warn_if_misrooted(args, reg, selected)
        findings = lint.run(rules) + lint.blind_spots()

        triple = self._triple(reg)
        # --quiet trims the detailed listing only. The vector and the snapshot keep
        # every INFO, because blind spots are declared, never silenced
        # (dictionary.yaml: slijepa-pjega) — a switch must not be able to turn
        # "not measured" into "measured clean".
        shown = [f for f in findings if f.severity != INFO] if args.quiet else findings
        rc = self._report(args, selected, shown, findings, triple)
        if args.snapshot:
            self._write_snapshot(args, selected, findings, triple)
        if args.graph:
            self._render_graph(args, lint)
        return rc

    # `acronym_identifier_casing.status` values that put criterion 4 in force.
    # The Croatian form is accepted because the discourse registry the criterion
    # was cut from still carries its own status vocabulary.
    _STATUS_ADOPTED = frozenset({"adopted", "usvojen"})

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
        if not isinstance(doc, dict) or "domains" not in doc:
            raise KeyError(
                "no `domains` key — expected the criterion dictionary.json "
                "(converted from dictionary.yaml#code on 2026-07-29)"
            )
        # JSON carries no comments: underscore-prefixed keys are the dictionary's
        # prose and are dropped before the rules see it.
        reg = {k: v for k, v in doc.items() if not k.startswith("_")}
        reg["acronyms"] = reg.get("identifier_acronyms", [])
        casing = reg.get("acronym_identifier_casing") or {}
        status = casing.get("status")
        reg["acronym_severity"] = ERROR if status in Application._STATUS_ADOPTED else WARNING
        reg["acronym_pending"] = casing.get("decision_pending", "an open DR")
        # The reproducibility triple names the criterion (the code vocabulary) and
        # the discourse revision it was cut from — versioned apart from each other.
        reg["registry_version"] = reg.get("criterion_version", "unversioned")
        reg["dictionary_version"] = reg.get("dictionary_version", "unversioned")
        return reg

    @staticmethod
    def _triple(reg: dict) -> dict[str, str]:
        # Reproducibility triple — dictionary.yaml: `trojka-reproducibilnosti`.
        # A finding without it is not reproducible, so it is printed with every
        # report and stored with every snapshot.
        return {
            "tool": f"wem_lint {__version__}",
            # The criterion is the code vocabulary, versioned apart from the
            # discourse entries; both are named so a snapshot pins the exact file.
            "criterion": (
                f"dictionary.json {reg.get('registry_version', 'unversioned')}"
                f" (dictionary.yaml {reg.get('dictionary_version', 'unversioned')})"
            ),
            "platform": f"python {platform.python_version()} ({platform.system()})",
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
        text = self._graph_renderers[args.graph](lint.import_graph(), color=color)
        if args.graph_out:
            args.graph_out.write_text(text + "\n", encoding="utf-8")
            print(f"\nwem_lint: graph written to {args.graph_out}")
        else:
            print(f"\n{text}")

    def _register_graph_renderers(self) -> dict:
        # Format→renderer registry. Add a format here + its bound method; the parser
        # exposes the keys as --graph choices, _render_graph dispatches on them.
        return {"ascii": self._render_ascii_graph}

    def _render_ascii_graph(self, builder: ImportGraphBuilder, color: bool = True) -> str:
        """Render the package-level import DAG as a Unicode tree, tagging bad edges."""
        nodes, adj, viol, scope = builder.graph()

        def paint(text: str, code: str) -> str:
            return f"{code}{text}{self._RESET}" if color else text

        lines = [
            "=== NFR-ORG-01 — dependency graph (package level) ===",
            "  ▶ = imports;  a leaf tier (no outgoing edges) is the allowed foundation",
            "",
        ]
        for src in sorted(nodes):
            dsts = sorted(adj.get(src, ()))
            if not dsts:
                # In-scope & no outgoing = genuine leaf; out-of-scope = only ever a target.
                kind = (
                    "leaf — imports nothing intra-project"
                    if src in scope
                    else "external — not analysed as a source"
                )
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

        tags = (("CYCLE", "mutual"), ("LAYERING", "one-way"), ("LEAF", "misfiled leaf"))
        legend = "  ".join(paint(f"{t} ({d})", self._TAG_COLOUR[t]) for t, d in tags)
        lines.append(f"Legend: {legend}")
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

        print(f"\n== VECTOR {'=' * 60}")
        rows = self._vector(findings)
        if not rows:
            print("  (no findings)")
        for nfr, kind, sev, n in rows:
            print(f"  {nfr:<7} {kind:<24} {sev:<7} {n}")
        print(
            "  note: conformance vector — no aggregate score is defined for these\n"
            "  checks; the scale is nominal, so counting is the only admissible\n"
            "  operation (METHODOLOGY §3b/§6.1). A green vector proves conformance\n"
            "  to the declared criterion, not quality (dictionary: konformnost-vs-kvaliteta)."
        )

        print(f"\n== REPRODUCIBILITY {'=' * 52}")
        for key in ("tool", "criterion", "platform"):
            print(f"  {key:<10} {triple[key]}")
        if not triple["platform"].split()[1].startswith(triple["python_reference"]):
            print(
                f"  WARNING    registry pins python {triple['python_reference']}, running "
                f"{platform.python_version()} — the stdlib set tested is the\n"
                "             interpreter's, so ORG-01 scope is not reproducible against the pin"
            )

        print(f"\n{'-' * 60}")
        print(f"wem_lint: {errors} error(s), {warns} warning(s), {infos} info")
        print(
            "Notes: ORG-01 fan-in counts direct `wattleflow.helpers.<mod>` imports only; "
            "aggregate `from wattleflow.helpers import X` is not resolved, so fan-in is a "
            "lower bound (advisory). ORG-01 #2/#4 not yet automated. See NFR.md."
        )
        return 1 if errors else 0

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
            "reproducibility_triple": {k: triple[k] for k in ("tool", "criterion", "platform")},
            "python_reference": triple["python_reference"],
            "vector": [
                {"nfr": nfr, "kind": k, "severity": sev, "count": n}
                for nfr, k, sev, n in self._vector(findings)
            ],
            "blind_spots": [
                {"module": f.name, "reason": f.detail} for f in findings if f.nfr == "EXC"
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
                if f.nfr != "EXC"
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
            label = f"NFR-{nfr}" if nfr in RuleFactory.available() else f"{nfr} (blind spots)"
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

        groups: dict[str, list[Finding]] = {}
        rest: list[Finding] = []
        ordered = sorted(findings, key=lambda f: (-f.severity, f.kind or "", str(f.path), f.line))
        for f in ordered:
            if f.kind in self._CATALOGUE:
                groups.setdefault(f.kind, []).append(f)
            else:
                rest.append(f)

        for kind, items in groups.items():
            c = self._CATALOGUE[kind]
            sev = items[0].severity
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
            print(f"\n{dim}--- other findings (no friendly entry yet) ---{reset}")
            for f in rest:
                print(f.render(args.src))


if __name__ == "__main__":
    raise SystemExit(Application().run())
# --------------------------------------------------------------------------- #
# endregion Application                                                       #
# --------------------------------------------------------------------------- #
