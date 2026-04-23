# Module name: documents/wattle.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# Dependencies:
#   pip install rdflib
#
# --------------------------------------------------------------------------- #

"""
Description: This module defines the Wattle RDF document and WattleGraphBuilder
for constructing provenance-aware RDF graphs within the WattleFlow framework.
"""

from __future__ import annotations
import logging
import re
from abc import ABC
from datetime import datetime, timezone
from typing import Iterable, Optional

try:
    from rdflib import Graph, Namespace, URIRef, Node, Literal
    from rdflib.namespace import DCAT, DCTERMS, PROV, RDF
except Exception as e:
    raise ModuleNotFoundError(
        f"You need rdflib for documents/wattle.py.\n"
        "Please run: pip install rdflib! {str(e)}"
    ) from e

from uuid import uuid4
from wattleflow.core import IWattleflow
from wattleflow.core.creational import IBuilder
from wattleflow.concrete import AuditLogger, Document
from wattleflow.constants import Event, MimeTypes


_URI_SAFE: re.Pattern = re.compile(r"[^A-Za-z0-9_\-.]")


# region global methods
def _safe_uri_segment(value: str) -> str:
    """Return *value* with any character unsafe in a URI path segment replaced by ``_``."""
    return _URI_SAFE.sub("_", value)


def _require_non_empty_str(value: object, name: str) -> str:
    """Raise :exc:`ValueError` if *value* is not a non-empty string; otherwise return it."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string, got {value!r}")
    return value


# endregion global methods


class WattleGraphBuilder(IBuilder, AuditLogger, ABC):
    # Class-level namespace constants — read-only, shared across all instances.
    WG: Namespace = Namespace("urn:wattle:vocab#")
    RES: Namespace = Namespace("urn:wattle:resource:")
    NFO: Namespace = Namespace(
        "http://www.semanticdesktop.org/ontologies/2007/03/22/nfo#"
    )

    def __init__(
        self,
        caller: IWattleflow,
        mime: MimeTypes,
        uri: str,
        level: int = logging.NOTSET,
        handler: Optional[logging.Handler] = None,
        **kwargs,
    ) -> None:
        AuditLogger.__init__(self, level=level, handler=handler)

        _require_non_empty_str(uri, "uri")
        if not isinstance(mime, MimeTypes):
            raise TypeError(f"mime must be a MimeTypes instance, got {type(mime)!r}")
        if not isinstance(caller, IWattleflow):
            raise TypeError(
                f"caller must be an IWattleflow instance, got {type(caller)!r}"
            )

        self._caller: IWattleflow = caller
        self._mime: MimeTypes = mime
        self._uri: str = uri
        self._graph_identifier: Optional[str] = None

        self.debug(
            msg=Event.Constructor.value,
            step=Event.Completed.value,
            uri=uri,
        )

    @property
    def graph_identifier(self) -> Optional[str]:
        """URN of the graph produced by the most recent :meth:`build` call, or ``None``."""
        return self._graph_identifier

    # region IBuilder contract
    def build(self) -> Graph:
        """Construct and return a fully populated provenance :class:`~rdflib.Graph`."""
        self.debug(msg=Event.Constructor.value, step=Event.Started.value)

        identifier = uuid4()
        self._graph_identifier = f"urn:wattleflow:graph:{identifier}"
        graph = Graph(identifier=URIRef(self._graph_identifier))

        self._bind_namespaces(graph)

        # FIX: v0.0.0.62 - 26/3/17 - Sanitised caller.name and mime values before
        # using them in URIRef construction; raw strings could inject arbitrary URI
        # characters and produce malformed or exploitable graph identifiers.
        caller_seg: str = _safe_uri_segment(self._caller.name)
        mime_name_seg: str = _safe_uri_segment(self._mime.name)
        mime_value_seg: str = _safe_uri_segment(self._mime.value)

        subject: URIRef = self.RES["wattle"]

        self._add_artifact(graph, subject)
        self._add_format(graph, mime_name_seg)
        self._add_steps(graph, caller_seg)
        self._add_provenance(graph, caller_seg, mime_name_seg, mime_value_seg)

        self.debug(msg=Event.Constructor.value, step=Event.Completed.value)
        return graph

    # --- Protected helpers ---------------------------------------------------

    def _bind_namespaces(self, graph: Graph) -> None:
        """Bind all standard namespaces onto *graph*."""
        for pfx, ns in [
            ("WG", self.WG),
            ("RES", self.RES),
            ("DCAT", DCAT),
            ("PROV", PROV),
            ("NFO", self.NFO),
            ("DCTERMS", DCTERMS),
        ]:
            graph.bind(pfx, ns)

    def _add_artifact(self, graph: Graph, subject: URIRef) -> None:
        """Add artefact-type and processor triples to *graph*."""
        graph.add((subject, RDF.type, self.WG.Processor))
        graph.add((subject, self.WG.Processor, Literal(self._caller.name)))
        graph.add((subject, RDF.type, self.WG.Artifact))
        graph.add((subject, RDF.type, DCAT.Distribution))
        # FIX: v0.0.0.62 - 26/3/17 - DCAT.record is not a valid DCAT predicate for
        # recording a MIME type; replaced with DCAT.mediaType for semantic correctness.
        # Old: graph.add((subject, RDF.type, DCAT.record))
        # Old: graph.add((subject, DCAT.record, Literal(self._mime.name)))
        graph.add((subject, DCAT.mediaType, Literal(self._mime.name)))
        graph.add((subject, RDF.type, self.WG.Created))
        # FIX: v0.0.0.62 - 26/3/17 - Replaced datetime.now() with timezone-aware
        # datetime.now(timezone.utc) to avoid naive timestamps.
        # Old: graph.add((subject, self.WG.runId, Literal(str(self.utc_time_stamp()))))
        graph.add((subject, self.WG.runId, Literal(str(datetime.now(timezone.utc)))))

    def _add_format(self, graph: Graph, mime_name_seg: str) -> None:
        """Add DCTERMS format triple to *graph*."""
        graph.add((self.RES[mime_name_seg], DCTERMS.format, Literal(self._mime.value)))

    def _add_steps(self, graph: Graph, caller_seg: str) -> None:
        """Add step triples to *graph*."""
        graph.add((self.RES[caller_seg], RDF.type, self.WG.Step))
        graph.add((self.RES[caller_seg], self.WG.hasStep, Literal("Creation")))

    def _add_provenance(
        self,
        graph: Graph,
        caller_seg: str,
        mime_name_seg: str,
        mime_value_seg: str,
    ) -> None:
        """Add PROV provenance triples to *graph*."""
        graph.add((self.RES[caller_seg], PROV.used, self.RES[mime_name_seg]))
        graph.add((self.RES[caller_seg], PROV.generated, self.RES[mime_value_seg]))

    # endregion IBuilder contract


# region FIX: v0.0.0.62 - 26/3/17 - Refactored Wattle.__init__: all graph-construction
# logic delegated to WattleGraphBuilder.build(). Added explicit @property accessors
# for uri, subject, WG, RES, and NFO (previously relied on __getattr__ forwarding
# to the metadata dict, which raised ValueError instead of AttributeError and
# silently broke hasattr() checks). Removed __getattr__ as PresetDecorator is not
# used here. Fixed remove(): self._subject (undefined) → self.subject (property).
# Fixed add(): subject type hint Namespace → URIRef (Namespace is not a valid RDF
# subject). Replaced all datetime.now() calls with self.utc_time_stamp().
# Added uri to metadata so the uri property can retrieve it — previously uri was
# logged but never stored.
# endregion FIX: v0.0.0.62 - 26/3/17 - Refactored Wattle.__init__: all graph-construction
class Wattle(Document[Graph], ABC):
    """An RDF-backed WattleFlow document representing a single provenance artefact."""

    def __init__(
        self,
        caller: IWattleflow,
        mime: MimeTypes,
        uri: str,
        level: int = logging.NOTSET,
        handler: Optional[logging.Handler] = None,
        **kwargs,
    ) -> None:

        builder = WattleGraphBuilder(
            caller=caller,
            mime=mime,
            uri=uri,
            level=level,
            handler=handler,
            **kwargs,
        )
        graph: Graph = builder.build()

        Document.__init__(self, content=graph, level=level, handler=handler)

        self._identifier = builder.graph_identifier

        self.debug(
            msg=Event.Constructor.value,
            step=Event.Started.value,
            identifier=self.identifier,
            level=level,
            handler=handler,
            uri=uri,
        )

        subject: URIRef = WattleGraphBuilder.RES["wattle"]
        self.update_metadata("subject", subject)
        self.update_metadata("uri", uri)
        self.update_metadata("WG", WattleGraphBuilder.WG)
        self.update_metadata("RES", WattleGraphBuilder.RES)
        self.update_metadata("DCAT", DCAT)
        self.update_metadata("PROV", PROV)
        self.update_metadata("NFO", WattleGraphBuilder.NFO)

        self.debug(
            msg=Event.Constructor.value,
            step=Event.Completed.value,
        )

    # ----------------------------------------------------------
    # region Properties
    # ----------------------------------------------------------

    @property
    def namespaces(self) -> Iterable[tuple[str, URIRef]]:
        return self.content.namespace_manager.namespaces()

        # region ignore
        # def namespacemap(self):
        # ns_map = dict(self.content.namespace_manager.namespaces())
        # ns = ns_map.get("schema")
        # for _, uri in ns_map.items():
        #     u = str(uri).rstrip("/")
        #     if u in ("http://schema.org", "https://schema.org"):
        #         return Namespace(uri)
        # raise ValueError("Schema is not found!")
        # endregion ignore

    @property
    def size(self) -> int:
        if isinstance(self.content, Graph):
            return len(self.content)
        return 0

    @property
    def uri(self) -> str:
        return str(self.metadata.get("uri", ""))

    @property
    def subject(self) -> URIRef:
        return self.metadata["subject"]  # type: ignore[return-value]

    @property
    def WG(self) -> Namespace:
        return self.metadata["WG"]  # type: ignore[return-value]

    @property
    def RES(self) -> Namespace:
        return self.metadata["RES"]  # type: ignore[return-value]

    @property
    def NFO(self) -> Namespace:
        return self.metadata["NFO"]  # type: ignore[return-value]

    # endregion Properties

    def specific_request(self) -> "Wattle":
        return self

    # region FIX: v0.0.0.62 - 26/3/17 - Corrected subject parameter type from Namespace
    # to URIRef; rdflib requires a Node (URIRef or BNode) as a triple subject,
    # not a Namespace instance.
    # Old: def add(self, subject: Namespace, predicate: URIRef, value: str):
    # endregion FIX: v0.0.0.62 - 26/3/17 - Corrected subject parameter type from Namespace
    def add(self, subject: URIRef, predicate: URIRef, value: str) -> None:
        self._content.add((subject, predicate, Literal(value)))  # type: ignore
        # Old: self._lastchange = datetime.now()
        self._lastchange = self.utc_time_stamp()

    def add_predicate(self, predicate: URIRef, value: str) -> None:
        self._content.add((self.subject, predicate, Literal(value)))  # type: ignore
        # Old: self._lastchange = datetime.now()
        self._lastchange = self.utc_time_stamp()

    # FIX: v0.0.0.62 - 26/3/17 - Fixed undefined self._subject → self.subject (property).
    # Old: self._content.remove((self._subject, predicate, Literal(value)))
    def remove(self, predicate: URIRef, value: object) -> None:
        self._content.remove((self.subject, predicate, Literal(value)))  # type: ignore
        # Old: self._lastchange = datetime.now()
        self._lastchange = self.utc_time_stamp()

    def clear(self) -> None:
        self._content.remove((None, None, None))  # type: ignore
        self._content = Graph(identifier=self.subject)  # type: ignore
        # Old: self._lastchange = datetime.now()
        self._lastchange = self.utc_time_stamp()

    def get(self, predicate: URIRef, default: Optional[Node] = None) -> Optional[Node]:
        try:
            result = self._content.value(  # type: ignore
                subject=self.subject,  # type: ignore
                predicate=predicate,
                default=default,
            )
            return result
        except Exception as e:
            self.error(msg=Event.Getting.value, error=str(e))
            return default

    def update_graph(self, new_graph: Graph) -> None:
        copied = Graph(identifier=new_graph.identifier)

        for triple in new_graph:
            copied.add(triple)

        for prefix, ns in new_graph.namespaces():
            copied.bind(prefix, ns, override=True)

        self.update_content(copied)

    # region FIX: v0.0.0.62 - 26/3/17 - Removed __getattr__: it raised ValueError instead
    # of AttributeError, silently breaking hasattr() and any code that relies on
    # the standard attribute-lookup protocol. All previously accessed metadata keys
    # (subject, WG, RES, NFO, uri) are now exposed as explicit @property accessors.
    # PresetDecorator is not used in this class, so __getattr__ forwarding is
    # unnecessary.
    # Old:
    # def __getattr__(self, name: str) -> object:
    #     obj = self.metadata.get(name, None)
    #     if obj is None:
    #         raise ValueError(f"Property: {name} does not exist in the document!")
    #     return obj
    # endregion FIX: v0.0.0.62 - 26/3/17 - Removed __getattr__: it raised ValueError instead
