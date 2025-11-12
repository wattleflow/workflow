# Module name: graph_html.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


from __future__ import annotations
import logging
from abc import ABC
from datetime import datetime
from pathlib import Path
from rdflib import Graph, Literal, Namespace, Node, URIRef
from typing import Optional

from wattleflow.core import (
    IPipeline,
    IProcessor,
    IRepository,
    ITarget,
    IWattleflow,
)

from wattleflow.concrete import (
    Document,
    DocumentFacade,
    StrategyCreate,
    StrategyRead,
    StrategyWrite,
)
from wattleflow.constants import Event
from wattleflow.drivers import FileTypes
from wattleflow.helpers import Attribute, Normaliser


# document: rdf ---------------------------------------------------------------
class GraphHtml(Document[Graph]):
    def __init__(
        self,
        uri: str,
        html: str,
        level: int = logging.NOTSET,
        handler: Optional[logging.Handler] = None,
    ):
        graph = Graph()
        namespace = Namespace("urn:wattleflow:htmlgraph#")
        subject = URIRef(f"urn:wattleflow:htmlgraph:{uri}")
        graph.bind("ex", namespace)
        graph.bind("doc", subject)

        Document.__init__(self, content=graph, level=level, handler=handler)
        self.update_metadata("namespace", namespace)
        self.update_metadata("subject", subject)

        self.debug(
            msg=Event.Constructor.value,
            step=Event.Started.value,
            level=level,
            handler=handler,
            uri=uri,
        )

        self.add_predicate(document.namespace.hasUri, uri)  # type: ignore
        self.add_predicate(document.namespace.hasIdentifier, hash(self))  # type: ignore
        self.add_predicate(document.namespace.hasNamespace, EX)  # type: ignore
        self.add_predicate(document.namespace.hasSubject, DOC)  # type: ignore
        self.add_predicate(document.namespace.hasCreatedAt, datetime.now())  # type: ignore

        self.debug(
            msg=Event.Constructor.value,
            step=Event.Completed.value,
        )

    @property
    def uri(self) -> str:
        return self.get(URIRef("hasUri"), self.identifier)  # type: ignore
        # return self.get(URIRef(document.namespace.hasUri), "")

    @property
    def identifier(self) -> str:
        return self.identifier

    @property
    def size(self) -> int:
        if isinstance(self.content, Graph):
            return len(self.content)
        return 0

    @property
    def graph(self) -> Graph:
        return self._content  # type: ignore

    def specific_request(self) -> "GraphHtml":
        return self

    def add_predicate(self, predicate: URIRef, value: str):
        self._content.add((self.subject, predicate, Literal(value)))  # type: ignore
        self._lastchange = datetime.now()

    def remove(self, predicate: URIRef, value: object):
        self._content.remove((self._subject, predicate, Literal(value)))  # type: ignore
        self._lastchange = datetime.now()

    def clear(self):
        self._content.remove((None, None, None))  # type: ignore
        self._content = Graph(identifier=self.subject)  # type: ignore
        self._lastchange = datetime.now()

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

    def update_graph(self, new_graph: Graph):
        copied = Graph(identifier=new_graph.identifier)

        for triple in new_graph:
            copied.add(triple)

        for prefix, ns in new_graph.namespaces():
            copied.bind(prefix, ns, override=True)

        self.update_content(copied)

    def __getattr__(self, name: str) -> object:
        obj = self.metadata.get(name, None)
        if obj is None:
            raise ValueError(f"Property: {name} does not exist in the document!")
        return obj


# document handling strategies ------------------------------------------------
class CreateGraphFromHtml(StrategyCreate):
    def execute(self, caller: IWattleflow, *args, **kwargs) -> Optional[ITarget]:
        self.debug(
            msg=Event.Execute.value,
            step=Event.Started.value,
            caller=caller,
            kwargs=len(kwargs),
        )
        downloaded_at = datetime.now()

        Attribute.evaluate(caller=self, target=caller, expected_type=IProcessor)
        Attribute.mandatory(self, "uri", str, **kwargs)
        Attribute.mandatory(self, "content", str, **kwargs)
        Attribute.mandatory(self, "metadata", dict, **kwargs)

        if not len(self.content) > 0:  # type: ignore
            self.warning(
                msg=Event.Execute.value,
                error="Web page's feeling a bit empty today!",
                uri=self.uri,  # type: ignore
            )
            return

        document: GraphHtml = Graph(source=self.uri)  # type: ignore
        facade: DocumentFacade = DocumentFacade(document)

        # graph metadata: predicate, value
        document.add_predicate(document.namespace.hasIdentifier, facade.identifier)  # type: ignore
        document.add_predicate(document.namespace.hasUri, self.uri)  # type: ignore
        document.add_predicate(
            document.namespace.hasSource, self.metadata.get("source", "?")  # type: ignore
        )
        document.add_predicate(
            document.namespace.hasTitle, self.metadata.get("title", "?")  # type: ignore
        )
        document.add_predicate(
            document.namespace.hasDescription, self.metadata.get("description", "?")  # type: ignore
        )
        document.add_predicate(document.namespace.hasDownloadedAt, downloaded_at)  # type: ignore
        document.add_predicate(
            document.namespace.hasDownloadedBy, self.processor.name  # type: ignore
        )
        document.add_predicate(document.namespace.hasFileName, self.filename)  # type: ignore
        document.add_predicate(
            document.namespace.hasLinks, self.metadata.get("links", "?")  # type: ignore
        )
        document.add_predicate(
            document.namespace.hasFileSize, self.metadata.get("filesize", "")  # type: ignore
        )
        document.add_predicate(document.namespace.hasContent, self.content)  # type: ignore
        document.add_predicate(document.namespace.hasTranscript, "")  # type: ignore

        self.info(
            msg=Event.Created.value,
            step=Event.Completed.value,
            document=document,
            size=document.size,
        )

        return facade


class ReadHtmlGraphDocument(StrategyRead, ABC):
    def execute(self, caller: IWattleflow, *args, **kwargs) -> ITarget | None:
        return super().execute(caller, *args, **kwargs)


class WriteGraphHtmlDocument(StrategyWrite):
    def get_schema_ns(self, graph: Graph) -> Namespace:
        ns_map = dict(graph.namespace_manager.namespaces())
        ns = ns_map.get("schema")
        if ns is not None:
            return Namespace(ns)

        for _, uri in ns_map.items():
            u = str(uri).rstrip("/")
            if u in ("http://schema.org", "https://schema.org"):
                return Namespace(uri)

        raise ValueError("Schema is not found!")

    def execute(self, caller: IWattleflow, facade: ITarget, *args, **kwargs) -> bool:
        self.debug(
            msg=Event.Execute.value,
            caller=caller,
            facade=facade,
            **kwargs,
        )

        Attribute.evaluate(caller=self, target=caller, expected_type=IPipeline)
        Attribute.mandatory(caller=self, name="repository", cls=IRepository, **kwargs)
        Attribute.mandatory(caller=self, name="processor", cls=IProcessor, **kwargs)

        graph: GraphHtml = facade.request()  # type: ignore
        Attribute.evaluate(self, graph, expected_type=GraphHtml)
        Attribute.evaluate(self, graph.content, expected_type=Graph)

        if not graph.size > 0:  # type: ignore
            self.warning(
                msg=Event.Execute.value,
                graph=graph,
                error="Is this graph half empty or half full?",
            )
            return False

        suffix = kwargs.get("suffix", ".json")
        name = graph.get(URIRef("hasFilename"), graph.identifier)  # type: ignore
        filename = Path(name).with_suffix(suffix)  # type: ignore

        sheetname = graph.get(URIRef("hasSheetname"), None)  # type: ignore
        if sheetname is None:
            sheetname: str = graph.metadata.get("sheetname", None)
            if sheetname:
                filename = filename.with_stem(
                    "%s-%s" % filename.stem % Normaliser.transform(sheetname)
                )
        self.debug(
            msg=Event.Execute.value,
            step=Event.Completed.value,
            filename=str(filename),
            sheetname=sheetname,
        )

        ns_map = dict(graph.content.namespace_manager.namespaces())  # type: ignore
        EX = Namespace(ns_map.get("ex", "https://example.org/"))
        subject = URIRef(graph.content.identifier)  # type: ignore

        for key, value in graph.metadata.items():
            predicate = EX[key]
            graph.content.add((subject, predicate, Literal(value)))  # type: ignore

        # update metadata
        graph.update_metadata("storage_pipeline", caller.name.lower())
        graph.update_metadata("storage_time", graph.utc_)

        output = self.repository.driver.write(  # type: ignore
            filename=filename.name,
            ftype=FileTypes.GRAPH,
            data=graph.content,
            subdir=caller.name.lower(),
            mkdir=True,
            destination=filename,
            format="json-ld",
            indent=2,
        )

        graph.update_metadata("storage_filename", output)

        self.debug(
            msg=Event.Execute.value,
            step=Event.Completed.value,
            document=graph,
            output=output,  # type: ignore
            size=graph.size,
        )

        return True
