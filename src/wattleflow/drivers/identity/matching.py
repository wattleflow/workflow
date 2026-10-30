# Module name: drivers/identity/matching.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""Blocking, the probabilistic model, learning, decision, grouping and quality
of the identity driver (SyRS-DRV-identity §2.5 steps 3, 5–8 and 10)."""

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations

__all__ = [
    "Blocking",
    "Bridges",
    "ComparisonVector",
    "Decision",
    "ExpectationMaximisation",
    "FellegiSunter",
    "LinkageQuality",
    "UnionFind",
]

import math
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from wattleflow.core import IStrategy, IWattleflow
from wattleflow.concrete.base import Wattleflow
from wattleflow.drivers.identity.similarity import JaroWinkler, NGramJaccard, Soundex

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Blocking and comparison                                              #
# --------------------------------------------------------------------------- #


class Blocking:
    """Step 3: keys that put likely pairs in the same block, so a value is
    compared with a few candidates and not with every identity."""

    PREFIX = 3

    @classmethod
    def keys(cls, value: str) -> list[str]:
        words = value.split()
        if not words:
            return []
        keys = [f"p:{value[: cls.PREFIX]}", f"s:{Soundex.encode(words[-1])}"]
        return [k for k in dict.fromkeys(keys) if not k.endswith(":")]


class ComparisonVector:
    """Step 4 for statistical kinds: each comparator gives a level, 0 the
    strongest agreement. The cut-offs define the model's levels."""

    LEVELS: Mapping[str, tuple[float, ...]] = {
        "jaro_winkler": (0.95, 0.88),
        "jaccard": (0.8, 0.5),
        "soundex": (1.0,),
    }

    @classmethod
    def compare(cls, left: str, right: str) -> dict[str, int]:
        scores = {
            "jaro_winkler": JaroWinkler.similarity(left, right),
            "jaccard": NGramJaccard.similarity(left, right),
            "soundex": Soundex.similarity(left.split()[-1] if left else "", right.split()[-1] if right else ""),
        }
        return {name: cls._level(score, cls.LEVELS[name]) for name, score in scores.items()}

    @classmethod
    def levels(cls, comparator: str) -> int:
        return len(cls.LEVELS[comparator]) + 1

    @staticmethod
    def _level(score: float, cuts: Sequence[float]) -> int:
        for level, cut in enumerate(cuts):
            if score >= cut:
                return level
        return len(cuts)


# --------------------------------------------------------------------------- #
# endregion Blocking and comparison                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Model                                                                #
# --------------------------------------------------------------------------- #


class FellegiSunter(Wattleflow, IStrategy):
    """Step 5 (Fellegi and Sunter 1969): m and u per comparator level, weight
    log2(m/u), prior λ and the match probability.

    `m[c][l]` and `u[c][l]` are counts; add-one smoothing keeps every weight
    finite, so an unlearned model gives weight 0 and the prior decides.
    """

    __slots__ = ("_m", "_u", "_prior")

    def __init__(
        self,
        m: Mapping[str, Sequence[int]],
        u: Mapping[str, Sequence[int]],
        prior: float,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._m = {c: list(v) for c, v in m.items()}
        self._u = {c: list(v) for c, v in u.items()}
        self._prior = prior

    @staticmethod
    def _rates(counts: Sequence[int]) -> list[float]:
        total = sum(counts) + len(counts)
        return [(c + 1) / total for c in counts]

    def weights(self, comparator: str) -> list[float]:
        m, u = self._rates(self._m[comparator]), self._rates(self._u[comparator])
        raw = [math.log2(a / b) for a, b in zip(m, u, strict=False)]
        # Monotone: a stronger agreement level never weighs less than a weaker one.
        for level in range(len(raw) - 2, -1, -1):
            raw[level] = max(raw[level], raw[level + 1])
        return raw

    def weight(self, vector: Mapping[str, int], frequency: float | None = None) -> float:
        total = sum(self.weights(c)[level] for c, level in vector.items())
        if frequency and vector.get("jaro_winkler") == 0:
            # Term frequency: agreement on a rare value is stronger evidence.
            u_exact = self._rates(self._u["jaro_winkler"])[0]
            total += math.log2(u_exact / max(frequency, 1e-12))
        return total

    def probability(self, vector: Mapping[str, int], frequency: float | None = None) -> float:
        odds = math.log2(self._prior / (1 - self._prior)) + self.weight(vector, frequency)
        return 1.0 / (1.0 + 2.0 ** (-odds))

    def algorithm(self, caller: IWattleflow, **kwargs: Any) -> float:
        return self.probability(kwargs["vector"], kwargs.get("frequency"))


class ExpectationMaximisation(Wattleflow, IStrategy):
    """Step 6 (Dempster, Laird and Rubin 1977): estimates m, u and λ from
    comparison vectors of unlabelled pairs."""

    __slots__ = ()

    @staticmethod
    def estimate(
        vectors: Sequence[Mapping[str, int]],
        levels: Mapping[str, int],
        prior: float,
        iterations: int,
    ) -> tuple[dict[str, list[float]], dict[str, list[float]], float]:
        m = {c: [1.0 / (i + 1) for i in range(n)] for c, n in levels.items()}
        u = {c: [(i + 1) / n for i in range(n)] for c, n in levels.items()}
        for table in (m, u):
            for c in table:
                s = sum(table[c])
                table[c] = [v / s for v in table[c]]
        lam = prior
        for _ in range(iterations):
            posteriors = []
            for v in vectors:
                pm = lam * math.prod(m[c][lv] for c, lv in v.items())
                pu = (1 - lam) * math.prod(u[c][lv] for c, lv in v.items())
                posteriors.append(pm / (pm + pu) if pm + pu else 0.0)
            total = sum(posteriors)
            lam = min(max(total / len(vectors), 1e-6), 1 - 1e-6) if vectors else lam
            for c, n in levels.items():
                mc = [1e-6] * n
                uc = [1e-6] * n
                for g, v in zip(posteriors, vectors, strict=False):
                    mc[v[c]] += g
                    uc[v[c]] += 1 - g
                m[c] = [x / sum(mc) for x in mc]
                u[c] = [x / sum(uc) for x in uc]
        return m, u, lam

    def algorithm(self, caller: IWattleflow, **kwargs: Any) -> tuple:
        return self.estimate(kwargs["vectors"], kwargs["levels"], kwargs["prior"], kwargs["iterations"])


class Decision:
    """Step 7: two thresholds and one best candidate."""

    KNOWN, NEW, UNCERTAIN = "known", "new", "uncertain"

    @classmethod
    def decide(cls, scores: Sequence[tuple[str, float]], match: float, review: float) -> tuple[str, str | None]:
        if not scores:
            return cls.NEW, None
        ranked = sorted(scores, key=lambda s: s[1], reverse=True)
        best_token, best = ranked[0]
        runner_up = ranked[1][1] if len(ranked) > 1 else 0.0
        if best >= match and runner_up < match:
            return cls.KNOWN, best_token
        if best >= review:
            return cls.UNCERTAIN, None
        return cls.NEW, None


# --------------------------------------------------------------------------- #
# endregion Model                                                             #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Grouping                                                             #
# --------------------------------------------------------------------------- #


class UnionFind(Wattleflow, IStrategy):
    """Step 8: connected components of matched pairs within one call."""

    __slots__ = ("_parent",)

    def __init__(self, size: int, **kwargs) -> None:
        super().__init__(**kwargs)
        self._parent = list(range(size))

    def find(self, x: int) -> int:
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[max(ra, rb)] = min(ra, rb)

    def groups(self) -> dict[int, list[int]]:
        out: dict[int, list[int]] = {}
        for x in range(len(self._parent)):
            out.setdefault(self.find(x), []).append(x)
        return out

    def algorithm(self, caller: IWattleflow, **kwargs: Any) -> dict[int, list[int]]:
        for a, b in kwargs.get("pairs", ()):
            self.union(a, b)
        return self.groups()


class Bridges(Wattleflow, IStrategy):
    """Step 8 (Tarjan 1974): edges whose removal splits a group. A group held
    together by one such edge is weak; the driver does not merge across it."""

    __slots__ = ()

    @staticmethod
    def find(size: int, edges: Iterable[tuple[int, int]]) -> set[tuple[int, int]]:
        graph: dict[int, list[tuple[int, int]]] = {n: [] for n in range(size)}
        edge_list = list(edges)
        for index, (a, b) in enumerate(edge_list):
            graph[a].append((b, index))
            graph[b].append((a, index))
        order = [-1] * size
        low = [0] * size
        bridges: set[tuple[int, int]] = set()
        counter = 0
        for root in range(size):
            if order[root] != -1:
                continue
            stack = [(root, -1, iter(graph[root]))]
            order[root] = low[root] = counter
            counter += 1
            while stack:
                node, via, neighbours = stack[-1]
                advanced = False
                for nxt, index in neighbours:
                    if index == via:
                        continue
                    if order[nxt] == -1:
                        order[nxt] = low[nxt] = counter
                        counter += 1
                        stack.append((nxt, index, iter(graph[nxt])))
                        advanced = True
                        break
                    low[node] = min(low[node], order[nxt])
                if advanced:
                    continue
                stack.pop()
                if stack:
                    parent = stack[-1][0]
                    low[parent] = min(low[parent], low[node])
                    if low[node] > order[parent]:
                        bridges.add((min(parent, node), max(parent, node)))
        return bridges

    def algorithm(self, caller: IWattleflow, **kwargs: Any) -> set[tuple[int, int]]:
        return self.find(kwargs["size"], kwargs["edges"])


# --------------------------------------------------------------------------- #
# endregion Grouping                                                          #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Quality                                                              #
# --------------------------------------------------------------------------- #


class LinkageQuality:
    """Step 10: precision, recall and F1 over labelled pairs."""

    @staticmethod
    def measure(predicted: Iterable[tuple], actual: Iterable[tuple]) -> dict[str, float]:
        p = {tuple(sorted(x)) for x in predicted}
        a = {tuple(sorted(x)) for x in actual}
        hits = len(p & a)
        precision = hits / len(p) if p else 0.0
        recall = hits / len(a) if a else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        return {"precision": precision, "recall": recall, "f1": f1}


# --------------------------------------------------------------------------- #
# endregion Quality                                                           #
# --------------------------------------------------------------------------- #
