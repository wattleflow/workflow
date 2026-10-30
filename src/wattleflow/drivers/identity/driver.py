# Module name: drivers/identity/driver.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""The identity driver: finds entities, compares them with known identities and
returns content with identity keys and aliases (SyRS-DRV-identity)."""

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations

__all__ = ["DriverIdentity", "Identity", "Result"]

import hashlib
import hmac
import os
import random
from dataclasses import dataclass, field
from typing import Any

from wattleflow.core import IProduct
from wattleflow.concrete.driver import DriverMetadata, GenericDriver
from wattleflow.concrete.exception import DriverException
from wattleflow.drivers.identity.matching import (
    Blocking,
    Bridges,
    ComparisonVector,
    Decision,
    FellegiSunter,
    UnionFind,
)
from wattleflow.drivers.identity.recognition import (
    CheckDigit,
    EntityKinds,
    EntityRecognition,
    IdentityNormaliser,
    Mention,
)
from wattleflow.enums.capability import DriverCapability
from wattleflow.enums.event import Event

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Result                                                               #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Identity(IProduct):
    """One entity in the result. `token` is a key or an alias and never the
    entity's words (StRS BR13)."""

    location: tuple[int, int] | tuple[int, str]
    kind: str
    status: str
    token: str | None

    @property
    def name(self) -> str:
        return type(self).__name__


@dataclass(frozen=True, slots=True)
class Result(IProduct):
    """Content of the same type as the input, and its identities in order."""

    content: Any
    identities: list[Identity] = field(default_factory=list)

    @property
    def name(self) -> str:
        return type(self).__name__


# --------------------------------------------------------------------------- #
# endregion Result                                                            #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Driver                                                               #
# --------------------------------------------------------------------------- #


class DriverIdentity(GenericDriver):
    """First phase: the driver holds every algorithm (StRS BR17)."""

    ALLOWED = [
        "alias_key_env",
        "columns",
        "connection_manager",
        "connection_name",
        "context",
        "dictionary",
        "jurisdictions",
        "kinds",
        "language",
        "match_threshold",
        "model",
        "permit_write",
        "prior",
        "review_threshold",
        "titles",
        "token_length",
        "u_sample",
    ]
    LANGUAGES = ("en",)
    OPEN, CLOSE = "⟦", "⟧"
    SESSION = ("get", "set", "delete", "keys", "increment")

    __slots__ = ("_catalogue", "_key", "_kinds")

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._catalogue = EntityKinds.all()
        self._key: bytes | None = None
        self._kinds: dict[str, Any] = {}

    # region IDriver

    @classmethod
    def metadata(cls) -> DriverMetadata:
        return DriverMetadata(
            name=cls.__name__,
            version="1.0",
            protocol="identity",
            capabilities=[DriverCapability.READ.value, DriverCapability.WRITE.value],
        )

    def load(self) -> None:
        self.debug(msg=Event.Load, step=Event.Started)
        self._validate()
        secret = os.environ.get(self.alias_key_env)
        if not secret:
            raise DriverException(caller=self, error=f"environment variable {self.alias_key_env!r} is not set")
        self._key = secret.encode("utf-8")
        with self._connection().connect() as store:
            missing = [op for op in self.SESSION if not callable(getattr(store, op, None))]
        if missing:
            raise DriverException(caller=self, error=f"session lacks {', '.join(missing)}")
        self.debug(msg=Event.Load, step=Event.Completed)

    def close(self) -> None:
        self.debug(msg=Event.Close, step=Event.Started)
        self._key = None
        self.debug(msg=Event.Close, step=Event.Completed)

    def read(self, uri: str, **kwargs: Any) -> Any:
        return self._process(uri, kwargs.get("source"), kwargs.get("kinds"), persist=False)

    def write(self, uri: str, data: Any, **kwargs: Any) -> Any:
        if self.permit_write is not True:
            raise DriverException(caller=self, error="write is not permitted by configuration")
        return self._process(uri, data, kwargs.get("kinds"), persist=True)

    # endregion IDriver

    # region Configuration

    def _validate(self) -> None:
        for key in ("connection_name", "connection_manager", "alias_key_env", "token_length"):
            if getattr(self, key, None) in (None, ""):
                raise DriverException(caller=self, error=f"setting {key!r} is required")
        match, review, prior = self.match_threshold, self.review_threshold, self.prior
        if not all(isinstance(v, (int, float)) for v in (match, review, prior)):
            raise DriverException(caller=self, error="match_threshold, review_threshold and prior must be numbers")
        if not 0 < review < match < 1:
            raise DriverException(caller=self, error="thresholds must satisfy 0 < review < match < 1")
        if not 0 < prior < 1:
            raise DriverException(caller=self, error="prior must lie between 0 and 1")
        if not isinstance(self.token_length, int) or not 4 <= self.token_length <= 64:
            raise DriverException(caller=self, error="token_length must be an int from 4 to 64")
        if (self.language or "en") not in self.LANGUAGES:
            raise DriverException(caller=self, error=f"language {self.language!r} is not supported")
        self._kinds = self._kinds_of(self.kinds)

    def _kinds_of(self, codes: Any) -> dict[str, Any]:
        if codes is None:
            return dict(self._catalogue)
        unknown = EntityKinds.unknown(codes)
        if unknown:
            raise DriverException(caller=self, error=f"unknown entity kinds: {', '.join(unknown)}")
        return {c: self._catalogue[c] for c in codes}

    def _connection(self) -> Any:
        return self.connection_manager.get_connection(self.connection_name)

    # endregion Configuration

    # region Processing

    def _process(self, uri: str, source: Any, kinds: Any, persist: bool) -> Any:
        self.ensure_live()
        if not isinstance(uri, str) or not uri.strip():
            raise DriverException(caller=self, error="uri must be a non-empty namespace")
        selected = self._kinds_of(kinds) if kinds is not None else self._kinds
        action = "write" if persist else "read"
        if isinstance(source, list) and not source:
            return []
        self.debug(msg=Event.Process, step=Event.Started, action=action, kinds=len(selected))
        with self._connection().connect() as store:
            if isinstance(source, str):
                result: Any = self._text(store, uri, source, selected, persist)
            elif isinstance(source, list) and all(isinstance(r, dict) for r in source) and source:
                result = self._dataset(store, uri, source, selected, persist)
            elif isinstance(source, list):
                result = [self._text(store, uri, s, selected, persist) for s in source]
            else:
                raise DriverException(
                    caller=self, error=f"source must be text, a list of texts or rows, not {type(source).__name__}"
                )
        self.debug(msg=Event.Process, step=Event.Completed, action=action)
        return result

    def _text(self, store: Any, uri: str, text: str, kinds: dict, persist: bool) -> Result:
        clean = text.replace(self.OPEN, "[").replace(self.CLOSE, "]")
        recogniser = EntityRecognition(
            kinds=kinds,
            dictionary={**(self.dictionary or {}), **self._forms(store, uri, kinds)},
            titles=self.titles or (),
            context=self.context or {},
            jurisdictions=self.jurisdictions or (),
        )
        mentions = recogniser.find(clean)
        tokens = self._resolve(store, uri, mentions, persist)
        out, cursor, identities = [], 0, []
        for mention, (status, token) in zip(mentions, tokens, strict=False):
            identities.append(Identity((mention.start, mention.end), mention.kind, status, token))
            if token is None:
                continue
            out.append(clean[cursor : mention.start])
            out.append(token)
            cursor = mention.end
        out.append(clean[cursor:])
        return Result("".join(out), identities)

    def _dataset(self, store: Any, uri: str, rows: list[dict], kinds: dict, persist: bool) -> Result:
        columns = {c: k for c, k in (self.columns or {}).items() if k in kinds}
        mentions: list[Mention] = []
        places: list[tuple[int, str]] = []
        for r, row in enumerate(rows):
            for column, kind in columns.items():
                raw = row.get(column)
                if not isinstance(raw, str) or not raw.strip() or not self._valid(kind, raw):
                    continue
                value = IdentityNormaliser.value(kind, raw, self.titles or ())
                mentions.append(Mention(0, len(raw), kind, value))
                places.append((r, column))
        tokens = self._resolve(store, uri, mentions, persist)
        content = [dict(row) for row in rows]
        identities = []
        for (r, column), mention, (status, token) in zip(places, mentions, tokens, strict=False):
            identities.append(Identity((r, column), mention.kind, status, token))
            if token is not None:
                content[r][column] = token
        return Result(content, identities)

    def _valid(self, kind: str, raw: str) -> bool:
        if kind == "ACC":
            return CheckDigit.iban(raw) if raw[:2].isalpha() else CheckDigit.luhn(IdentityNormaliser.digits(raw))
        if kind in ("NID", "BID"):
            digits = IdentityNormaliser.digits(raw)
            checks = []
            if "AU" in (self.jurisdictions or ()):
                checks += [CheckDigit.tfn, CheckDigit.abn, CheckDigit.acn, CheckDigit.medicare]
            if "HR" in (self.jurisdictions or ()):
                checks.append(CheckDigit.oib)
            return any(check(digits) for check in checks)
        return True

    # endregion Processing

    # region Resolution

    def _statistical(self, kind: str) -> bool:
        return self._catalogue[kind].comparison == "statistical"

    def _resolve(self, store: Any, uri: str, mentions: list[Mention], persist: bool) -> list[tuple[str, str | None]]:
        decided: list[tuple[str, str | None]] = []
        fresh: list[int] = []
        for i, mention in enumerate(mentions):
            known = store.get(self._k(uri, "val", mention.kind, mention.value))
            if known:
                decided.append((Decision.KNOWN, known))
                continue
            status, token = (
                self._score(store, uri, mention) if self._statistical(mention.kind) else (Decision.NEW, None)
            )
            if status == Decision.NEW:
                token = self._alias(mention)
                fresh.append(i)
            decided.append((status, token))
        decided = self._group(store, uri, mentions, fresh, decided)
        if persist:
            self._persist(store, uri, mentions, decided)
        return decided

    def _score(self, store: Any, uri: str, mention: Mention) -> tuple[str, str | None]:
        candidates: dict[str, str] = {}
        for block in Blocking.keys(mention.value):
            for token in store.get(self._k(uri, "blk", mention.kind, block), []):
                record = store.get(self._k(uri, "id", token))
                if record:
                    candidates[token] = record["values"][0]
        if not candidates:
            return Decision.NEW, None
        model = self._model(store, uri, mention.kind)
        total = max(store.get(self._k(uri, "n", mention.kind), 0), 1)
        scores = []
        for token, value in candidates.items():
            vector = ComparisonVector.compare(mention.value, value)
            seen = store.get(self._k(uri, "tf", mention.kind, value), 0)
            scores.append((token, model.probability(vector, seen / total if seen else None)))
        return Decision.decide(scores, self.match_threshold, self.review_threshold)

    def _group(self, store: Any, uri: str, mentions: list[Mention], fresh: list[int], decided: list) -> list:
        """New entities of one call that match each other share one alias,
        except across a bridge of a larger group (BR06: when unsure, keep apart)."""
        nodes = [i for i in fresh if self._statistical(mentions[i].kind)]
        edges = []
        for a in range(len(nodes)):
            for b in range(a + 1, len(nodes)):
                left, right = mentions[nodes[a]], mentions[nodes[b]]
                if left.kind != right.kind or left.value == right.value:
                    continue
                model = self._model(store, uri, left.kind)
                vector = ComparisonVector.compare(left.value, right.value)
                if model.probability(vector) >= self.match_threshold:
                    edges.append((a, b))
        if not edges:
            return decided
        bridges = Bridges.find(len(nodes), edges)
        whole = UnionFind(len(nodes))
        for a, b in edges:
            whole.union(a, b)
        size = {m: len(g) for g in whole.groups().values() for m in g}
        kept = UnionFind(len(nodes))
        for a, b in edges:
            if (a, b) in bridges and size[a] > 2:
                continue
            kept.union(a, b)
        for members in kept.groups().values():
            for m in members[1:]:
                decided[nodes[m]] = decided[nodes[members[0]]]
        return decided

    def _persist(self, store: Any, uri: str, mentions: list[Mention], decided: list) -> None:
        sampler = random.Random(uri)
        for mention, (_status, token) in zip(mentions, decided, strict=False):
            if token is None:
                continue
            record_key = self._k(uri, "id", token)
            record = store.get(record_key)
            if record is None:
                record = {"kind": mention.kind, "values": [mention.value]}
                store.increment(self._k(uri, "n", mention.kind))
                self._learn_u(store, uri, mention, sampler)
            elif mention.value not in record["values"]:
                self._learn_m(store, uri, mention.kind, record["values"][0], mention.value)
                record["values"].append(mention.value)
            store.set(record_key, record)
            store.set(self._k(uri, "val", mention.kind, mention.value), token)
            store.increment(self._k(uri, "tf", mention.kind, mention.value))
            store.set(self._k(uri, "form", mention.kind, mention.value), token)
            for block in Blocking.keys(mention.value):
                key = self._k(uri, "blk", mention.kind, block)
                members = store.get(key, [])
                if token not in members:
                    store.set(key, members + [token])

    def _learn_m(self, store: Any, uri: str, kind: str, left: str, right: str) -> None:
        for comparator, level in ComparisonVector.compare(left, right).items():
            store.increment(self._k(uri, "m", kind, comparator, str(level)))

    def _learn_u(self, store: Any, uri: str, mention: Mention, sampler: random.Random) -> None:
        if not self._statistical(mention.kind):
            return
        others = [k for k in store.keys(self._k(uri, "id", "")) if store.get(k, {}).get("kind") == mention.kind]
        for key in sampler.sample(others, min(len(others), int(self.u_sample or 0))):
            for comparator, level in ComparisonVector.compare(mention.value, store.get(key)["values"][0]).items():
                store.increment(self._k(uri, "u", mention.kind, comparator, str(level)))

    def _model(self, store: Any, uri: str, kind: str) -> FellegiSunter:
        seed = self.model or {}
        tables: dict[str, dict[str, list[int]]] = {"m": {}, "u": {}}
        for table in tables:
            for comparator in ComparisonVector.LEVELS:
                base = list(seed.get(table, {}).get(comparator, [0] * ComparisonVector.levels(comparator)))
                tables[table][comparator] = [
                    base[level] + store.get(self._k(uri, table, kind, comparator, str(level)), 0)
                    for level in range(ComparisonVector.levels(comparator))
                ]
        return FellegiSunter(tables["m"], tables["u"], self.prior)

    def _forms(self, store: Any, uri: str, kinds: dict) -> dict[str, str]:
        forms = {}
        for kind in kinds:
            if self._catalogue[kind].recognition != "name":
                continue
            prefix = self._k(uri, "form", kind, "")
            for key in store.keys(prefix):
                forms[key[len(prefix) :]] = kind
        return forms

    def _alias(self, mention: Mention) -> str:
        digest = hmac.new(self._key or b"", f"{mention.kind}\x1f{mention.value}".encode("utf-8"), hashlib.sha256)
        return f"{self.OPEN}{mention.kind}:{digest.hexdigest().upper()[: self.token_length]}{self.CLOSE}"

    @staticmethod
    def _k(uri: str, *parts: str) -> str:
        return ":".join((uri, *parts))

    # endregion Resolution

    def __repr__(self) -> str:
        return f"{self.name}(state={self._fsm.state.name})"


# --------------------------------------------------------------------------- #
# endregion Driver                                                            #
# --------------------------------------------------------------------------- #
