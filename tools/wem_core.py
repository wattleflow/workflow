# Module name: tools/wem_core.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""wem_core — redesign scaffold (step 1) for wem_lint.

Separates the three concerns the current ORG-01 rule fuses into one class:

  * DependencyGraph — ONE shared model (static + relative + dynamic edges)
  * Metric          — diagnostics over the graph (NFR `[M]`; ANALIZA §5.8), never a gate
  * Rule            — conformance checks (ORG-01/02/03, SEC-03), pass/fail

Diagnostic (Metric) and managerial (Rule) are distinct types by construction — the
Goodhart wall of NFR `[M]` criterion 5 / ANALIZA §4.1. A Metric becomes a gate only via ADR.

This also dissolves the "same edge, opposite sign" defect: a foreign-import edge is read by
a Rule (SEC-03 → flag) and by a Metric (attack surface → count), never used to *exclude*.

Status: SCAFFOLD. Existing wem_lint.py rules migrate onto `Rule`; metrics are new. On
integration this maps onto the framework's IStrategy/IFactory dogfooding.
"""

from __future__ import annotations
import argparse
import ast
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable

__version__ = "0.3.0"  # scaffold; independent of NFR/ANALIZA versions


# --------------------------------------------------------------------------- #
# region Measurement — the NFR `[M]` charter, encoded                          #
# --------------------------------------------------------------------------- #
class Scale(Enum):
    """Stevens (1946) scale types; each Metric declares one, and only that
    scale's statistics are permitted (no summing across scales)."""

    NOMINAL = "nominal"
    ORDINAL = "ordinal"
    INTERVAL = "interval"
    RATIO = "ratio"


@dataclass(frozen=True)
class Measurement:
    """A diagnostic value under the `[M]` charter. It carries its scale and blind
    spots, and stays a diagnostic — never a gate — until an external criterion is
    attached (validated out-of-sample). `external_criterion is None` ⇒ not a gate."""

    name: str
    value: float
    scale: Scale
    unit: str
    blind_spots: tuple[str, ...] = ()
    external_criterion: str | None = None

    @property
    def gate_eligible(self) -> bool:
        return self.external_criterion is not None


@dataclass(frozen=True)
class Finding:
    """A conformance violation from a Rule (managerial; can fail the build)."""

    nfr: str
    severity: int
    module: str
    line: int
    message: str


# --------------------------------------------------------------------------- #
# endregion Measurement                                                        #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region DependencyGraph — the shared model                                   #
# --------------------------------------------------------------------------- #
class EdgeKind(Enum):
    STATIC = "static"      # absolute `import wattleflow…`
    RELATIVE = "relative"  # `from .x import Y` — current wem_lint blind spot
    DYNAMIC = "dynamic"    # ClassLoader / YAML string paths — blind spot


@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    kind: EdgeKind
    line: int = 0


class DependencyGraph:
    """Directed import graph. Reachability is computed over the transitive closure
    so propagation cost (change) and blast radius (security) read the *same* graph
    — the chaining of ANALIZA §5.2 / §5.5."""

    def __init__(self) -> None:
        self._out: dict[str, set[str]] = {}
        self.edges: list[Edge] = []

    def add_edge(self, e: Edge) -> None:
        if e.src == e.dst:
            return  # intra-module self-loop is noise
        self.edges.append(e)
        self._out.setdefault(e.src, set()).add(e.dst)
        self._out.setdefault(e.dst, set())

    @property
    def nodes(self) -> set[str]:
        return set(self._out)

    def _reach(self, start: str, adj: dict[str, set[str]]) -> set[str]:
        seen: set[str] = set()
        stack = list(adj.get(start, ()))
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            stack.extend(adj.get(n, ()))
        seen.discard(start)
        return seen

    def forward_reachable(self, n: str) -> set[str]:
        """Everything n transitively imports (fan-out closure)."""
        return self._reach(n, self._out)

    def reverse_reachable(self, n: str) -> set[str]:
        """Everything that transitively imports n (fan-in closure) — the
        supply-chain blast direction (a poisoned lib reaches its importers)."""
        rev: dict[str, set[str]] = {}
        for e in self.edges:
            rev.setdefault(e.dst, set()).add(e.src)
            rev.setdefault(e.src, set())
        return self._reach(n, rev)

    def transitive_pair_count(self) -> int:
        """Ordered (i, j), i≠j, joined by a directed path — numerator of
        MacCormack propagation cost."""
        return sum(len(self.forward_reachable(n)) for n in self._out)


# --------------------------------------------------------------------------- #
# endregion DependencyGraph                                                    #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Edge resolvers — close wem_lint's construct-validity blind spots      #
# --------------------------------------------------------------------------- #
class EdgeResolver(ABC):
    kind: EdgeKind

    @abstractmethod
    def resolve(self, module: str, package: str, tree: ast.AST) -> Iterable[Edge]: ...


class StaticImportResolver(EdgeResolver):
    """Absolute imports (module-level + lazy). This is all wem_lint sees today."""

    kind = EdgeKind.STATIC

    def resolve(self, module: str, package: str, tree: ast.AST) -> Iterable[Edge]:
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                yield Edge(module, node.module, self.kind, node.lineno)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    yield Edge(module, alias.name, self.kind, node.lineno)


class RelativeImportResolver(EdgeResolver):
    """Closes blind spot (1): `from .x import Y` / `from . import x`. wem_lint drops
    these (`parts[0] != 'wattleflow'`), under-counting intra-package coupling. The
    dot count (`node.level`) is resolved against the importing module's package."""

    kind = EdgeKind.RELATIVE

    @staticmethod
    def _absolute(package: str, level: int, module: str | None) -> str | None:
        # level 1 = current package; each extra dot climbs one parent.
        parts = package.split(".") if package else []
        up = level - 1
        if up > len(parts):
            return None
        base = parts[: len(parts) - up]
        target = ".".join((*base, module)) if module else ".".join(base)
        return target or None

    def resolve(self, module: str, package: str, tree: ast.AST) -> Iterable[Edge]:
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level and node.level > 0:
                dst = self._absolute(package, node.level, node.module)
                if dst:
                    yield Edge(module, dst, self.kind, node.lineno)


class DynamicImportResolver(EdgeResolver):
    """BLIND SPOT (2): `import_module(<str>)` in ClassLoader + class paths in YAML
    configs. The framework is config-driven, so a large share of true coupling is
    invisible to an import scan (ANALIZA construct-validity gap). Resolve from
    string literals and the YAML class-path graph."""

    kind = EdgeKind.DYNAMIC

    def resolve(self, module: str, package: str, tree: ast.AST) -> Iterable[Edge]:
        return ()  # TODO: scan import_module/ClassLoader str args + parse YAML paths


# --------------------------------------------------------------------------- #
# endregion Edge resolvers                                                      #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Metric — diagnostics (ANALIZA §5.8 vector), never a gate              #
# --------------------------------------------------------------------------- #
class Metric(ABC):
    name: str
    scale: Scale
    unit: str

    @abstractmethod
    def compute(self, g: DependencyGraph) -> Measurement: ...


class PropagationCost(Metric):
    """§5.8 Struktura. Share of ordered component pairs joined by a transitive
    dependency — the % of the system in reach of an average change (MacCormack).
    A true ratio-scale percentage (ANALIZA §5.1)."""

    name, scale, unit = "propagation_cost", Scale.RATIO, "fraction"

    def compute(self, g: DependencyGraph) -> Measurement:
        n = len(g.nodes)
        value = g.transitive_pair_count() / (n * (n - 1)) if n > 1 else 0.0
        return Measurement(
            self.name, value, self.scale, self.unit,
            blind_spots=("dynamic (ClassLoader/YAML) edges not resolved (lower bound)",),
        )


class BlastRadius(Metric):
    """§5.8 Izloženost (structural). Max reverse-reachability share over nodes —
    supply-chain blast (SEC-01/03): a compromised shared module reaches its
    importers (log4j). Reverse, not forward, is deliberate."""

    name, scale, unit = "blast_radius_max", Scale.RATIO, "fraction"

    def compute(self, g: DependencyGraph) -> Measurement:
        n = len(g.nodes)
        worst = max((len(g.reverse_reachable(x)) for x in g.nodes), default=0)
        value = worst / (n - 1) if n > 1 else 0.0
        return Measurement(
            self.name, value, self.scale, self.unit,
            blind_spots=("privilege/value weighting V not modelled; transitive deps only",),
        )


class AttackSurface(Metric):
    """§5.8 Izloženost. Manadhata–Wing: weighted count of exposed methods, channels
    and data items across the trust boundary. Needs interface extraction (AST) +
    the distribution manifest — not just the import graph."""

    name, scale, unit = "attack_surface", Scale.INTERVAL, "weighted-count"

    def compute(self, g: DependencyGraph) -> Measurement:
        raise NotImplementedError("SEC-02: interface/channel/data extraction pending")


class StructureCochangeNMI(Metric):
    """§5.8 Sklad. NMI between the static-dependency partition and the co-change
    partition (Gall/Zimmermann history). The one figure carrying information no
    single metric does (ANALIZA §5.9): does structure track change?"""

    name, scale, unit = "structure_cochange_nmi", Scale.RATIO, "0..1"

    def compute(self, g: DependencyGraph) -> Measurement:
        raise NotImplementedError("needs version-history co-change graph + community detection")


# --------------------------------------------------------------------------- #
# endregion Metric                                                             #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Rule — conformance (gate); existing wem_lint rules migrate here       #
# --------------------------------------------------------------------------- #
class Rule(ABC):
    nfr: str

    @abstractmethod
    def check(self, g: DependencyGraph, registry: dict) -> list[Finding]: ...

    # Migration targets (behaviour preserved, now over the shared graph):
    #   DependencyLocalityRule  → NFRQ-ORG-01   (helper→domain layering + fan-in)
    #   DistributionLocalityRule→ NFRQ-SEC-03   (foreign import = FLAG, not exclude)
    #   NomenclatureRule        → NFRQ-ORG-02   (AST name grammar; graph-independent)
    #   TypeVarRule             → NFRQ-ORG-03   (AST TypeVar roles; graph-independent)


# --------------------------------------------------------------------------- #
# endregion Rule                                                               #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Analysis — one graph, gate and diagnostics kept apart                 #
# --------------------------------------------------------------------------- #
class Analysis:
    """Runs Rules (gate → Findings) and Metrics (diagnostic → Measurements) over
    ONE shared graph, keeping the two apart — the diagnostic/managerial wall
    (NFR `[M]` criterion 5). The build fails on Rules only; a Metric never gates."""

    def __init__(self, graph: DependencyGraph, rules: list[Rule], metrics: list[Metric]):
        self._graph = graph
        self._rules = rules
        self._metrics = metrics

    def run(self, registry: dict) -> tuple[list[Finding], list[Measurement]]:
        findings = [f for r in self._rules for f in r.check(self._graph, registry)]
        measurements = [m.compute(self._graph) for m in self._metrics]
        return findings, measurements


# --------------------------------------------------------------------------- #
# endregion Analysis                                                           #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Source builder + CLI — metric calculations over real code            #
# --------------------------------------------------------------------------- #
def _module_name(path: Path, src: Path, prefix: str) -> str:
    parts = path.relative_to(src).with_suffix("").parts
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join((prefix, *parts))


def _package_name(path: Path, src: Path, prefix: str) -> str:
    # Package containing the module: raw path parts minus the last component —
    # the parent dir for a regular module, the dir itself for a package __init__.
    parts = path.relative_to(src).with_suffix("").parts
    return ".".join((prefix, *parts[:-1]))


def build_graph(src: Path, prefix: str = "wattleflow") -> DependencyGraph:
    """Build the module-level dependency graph from a source tree. STATIC + RELATIVE
    edges; the dynamic (ClassLoader/YAML) resolver is still a stub, so metrics remain
    a declared lower bound (NFR `[M]` blind-spot criterion)."""
    g = DependencyGraph()
    resolvers: list[EdgeResolver] = [StaticImportResolver(), RelativeImportResolver()]
    files = [p for p in src.rglob("*.py") if "__pycache__" not in p.parts]
    for path in files:
        module = _module_name(path, src, prefix)
        package = _package_name(path, src, prefix)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for r in resolvers:
            for e in r.resolve(module, package, tree):
                if e.dst.split(".")[0] == prefix:  # keep intra-project edges
                    g.add_edge(Edge(module, e.dst, e.kind, e.line))
    return g


def main(argv: list[str] | None = None) -> int:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description=f"wem_core {__version__} — NFR [M] metric calculations")
    ap.add_argument("--src", type=Path, default=here.parent / "src" / "wattleflow")
    ap.add_argument("--prefix", default="wattleflow")
    ap.add_argument("--top", type=int, default=12, help="per-node hub rows to show (0 = all)")
    ap.add_argument("--version", action="version", version=f"wem_core {__version__}")
    args = ap.parse_args(argv)

    if not args.src.exists():
        print(f"wem_core: source tree not found: {args.src}", file=sys.stderr)
        return 2

    g = build_graph(args.src, args.prefix)
    metrics: list[Metric] = [PropagationCost(), BlastRadius()]

    print(f"=== wem_core {__version__} — metrike (dijagnostika, NFR [M]) ===")
    print(f"src: {args.src}   modula (čvorova): {len(g.nodes)}   bridova: {len(g.edges)}\n")
    for m in metrics:
        try:
            r = m.compute(g)
        except NotImplementedError as e:
            print(f"  {m.name:<20} — (nije implementirano: {e})")
            continue
        gate = "gate-eligible" if r.gate_eligible else "DIJAGNOSTIKA (ne gate — nema vanjskog kriterija)"
        print(f"  {r.name:<20} = {r.value:.4f} [{r.scale.value}, {r.unit}]  {gate}")
        for bs in r.blind_spots:
            print(f"  {'':<20}   slijepa točka: {bs}")

    # Per-node diagnostic (SEC-01 blast + fan-out reach) — surfaces the hubs, not
    # just the max. blast = share of tree that transitively imports the node; reach
    # = share it transitively imports.
    n = len(g.nodes)
    top = args.top if args.top > 0 else n
    rows = sorted(
        (
            (
                len(g.reverse_reachable(x)) / (n - 1) if n > 1 else 0.0,
                len(g.forward_reachable(x)) / (n - 1) if n > 1 else 0.0,
                x,
            )
            for x in g.nodes
        ),
        reverse=True,
    )[:top]
    print(f"\n  Top-{top} hub po blast-u [ratio, udio stabla]:")
    print(f"  {'blast':>7}  {'reach':>7}  modul")
    for blast, reach, x in rows:
        print(f"  {blast:>7.3f}  {reach:>7.3f}  {x}")

    print("\nNapomena: STATIC + RELATIVE bridovi; dinamički (ClassLoader/YAML) nije razriješen")
    print("→ mjera je i dalje DONJA GRANICA (NFR [M], kriterij o slijepim točkama).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
# --------------------------------------------------------------------------- #
# endregion Source builder + CLI                                              #
# --------------------------------------------------------------------------- #
