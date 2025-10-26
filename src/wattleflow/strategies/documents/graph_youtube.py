# Module name: youtube_graph.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


from __future__ import annotations
import logging
from abc import ABC
from datetime import datetime
from pathlib import Path
from rdflib import Graph, Literal, Namespace, Node, URIRef
from typing import Dict, List, Optional

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
    StrategyWrite,
)
from wattleflow.constants import Event
from wattleflow.drivers import FileTypes
from wattleflow.helpers import (
    Attribute,
)


class YoutubeGraph(Document[Graph], ABC):  # type: ignore
    def __init__(
        self,
        source: str,
        level: int = logging.NOTSET,
        handler: Optional[logging.Handler] = None,
    ):
        graph = Graph()
        namespace = Namespace("urn:wattleflow:youtubegraph#")  # EX
        subject = URIRef(f"urn:wattleflow:youtubegraph:{source}")  # type: ignore # DOC
        graph.bind("ex", namespace)
        graph.bind("doc", subject)

        Document.__init__(self, content=graph, level=level, handler=handler)
        self.update_metadata("namespace", namespace)
        self.update_metadata("subject", subject)

    @property
    def graph(self) -> Graph:
        return self._content  # type: ignore

    @property
    def size(self) -> int:
        content = self.metadata.get("transcript", [{}])
        return len(content)  # type: ignore

    @property
    def uri(self) -> str:
        return self.metadata.uri  # type: ignore

    def specific_request(self) -> "YoutubeGraph":
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


class CreateYoutubeDocument(StrategyCreate):
    def execute(self, caller: IWattleflow, *args, **kwargs) -> Optional[ITarget]:
        self.debug(
            msg=Event.Execute.value,
            step=Event.Started.value,
            caller=caller,
            kwargs=len(kwargs),
        )

        Attribute.evaluate(caller=self, target=caller, expected_type=IProcessor)
        Attribute.mandatory(self, "id", str, **kwargs)
        Attribute.mandatory(self, "uri", str, **kwargs)
        Attribute.mandatory(self, "content", List, **kwargs)
        Attribute.mandatory(self, "metadata", Dict, **kwargs)

        if not len(self.content) > 0:  # type: ignore
            self.warning(
                msg=Event.Execute.value,
                error="Transcript's feeling a bit empty today!",
            )
            return

        document = YoutubeGraph(source=self.uri)  # type: ignore
        facade: DocumentFacade = DocumentFacade(document)

        # metadata
        document.update_metadata("id", self.id)  # type: ignore
        document.update_metadata("uri", self.uri)  # type: ignore
        document.update_metadata("source", "YouTube")
        document.update_metadata("created_by", caller.name)
        document.update_metadata("created_at", datetime.now())

        # graph metadata
        document.add_predicate(
            predicate=document.namespace.hasIdentifier,  # type: ignore
            value=facade.identifier,
        )
        document.add_predicate(
            predicate=document.namespace.hasId,  # type: ignore
            value=self.id,  # type: ignore
        )
        document.add_predicate(
            predicate=document.namespace.hasUri,  # type: ignore
            value=self.uri,  # type: ignore
        )
        document.add_predicate(
            predicate=document.namespace.hasSource,  # type: ignore
            value="YouTube",  # type: ignore
        )
        document.add_predicate(
            predicate=document.namespace.hasVideoId,  # type: ignore
            value=self.metadata.get("id", ""),  # type: ignore
        )
        document.add_predicate(
            predicate=document.namespace.hasUploader,  # type: ignore
            value=self.metadata.get("uploader", ""),  # type: ignore
        )
        document.add_predicate(
            predicate=document.namespace.hasTitle,  # type: ignore
            value=self.metadata.get("title", ""),  # type: ignore
        )
        document.add_predicate(
            predicate=document.namespace.hasDescription,  # type: ignore
            value=self.metadata.get("Description", ""),  # type: ignore
        )
        document.add_predicate(
            predicate=document.namespace.hasCategories,  # type: ignore
            value=self.metadata.get("categories", ""),  # type: ignore
        )
        document.add_predicate(
            predicate=document.namespace.hasTags,  # type: ignore
            value=self.metadata.get("tags", ""),  # type: ignore
        )
        document.add_predicate(
            predicate=document.namespace.hasAgeLimit,  # type: ignore
            value=self.metadata.get("age_limit", ""),  # type: ignore
        )
        document.add_predicate(
            predicate=document.namespace.hasUploaderId,  # type: ignore
            value=self.metadata.get("uploader_id", ""),  # type: ignore
        )
        document.add_predicate(
            predicate=document.namespace.hasUploaderUrl,  # type: ignore
            value=self.metadata.get("uploader_url", ""),  # type: ignore
        )
        document.add_predicate(
            predicate=document.namespace.hasChannelId,  # type: ignore
            value=self.metadata.get("channel_id", ""),  # type: ignore
        )
        document.add_predicate(
            predicate=document.namespace.hasChannelUrl,  # type: ignore
            value=self.metadata.get("channel_url", ""),  # type: ignore
        )
        document.add_predicate(
            predicate=document.namespace.hasUploadDate,  # type: ignore
            value=self.metadata.get("upload_date", ""),  # type: ignore
        )
        document.add_predicate(
            predicate=document.namespace.hasTimeStamp,  # type: ignore
            value=self.metadata.get("timestamp", ""),  # type: ignore
        )
        document.add_predicate(
            predicate=document.namespace.hasDuration,  # type: ignore
            value=self.metadata.get("duration", ""),  # type: ignore
        )
        document.add_predicate(
            predicate=document.namespace.hasViewCount,  # type: ignore
            value=self.metadata.get("view_count", ""),  # type: ignore
        )
        document.add_predicate(
            predicate=document.namespace.hasLikeCount,  # type: ignore
            value=self.metadata.get("like_count", ""),  # type: ignore
        )
        document.add_predicate(
            predicate=document.namespace.hasCommentCount,  # type: ignore
            value=self.metadata.get("comment_count", ""),  # type: ignore
        )

        document.add_predicate(
            predicate=document.namespace.hasLiveStatus,  # type: ignore
            value=self.metadata.get("live_status", ""),  # type: ignore
        )
        document.add_predicate(
            predicate=document.namespace.hasResolution,  # type: ignore
            value=self.metadata.get("resolution", ""),  # type: ignore
        )
        document.add_predicate(
            predicate=document.namespace.hasHeight,  # type: ignore
            value=self.metadata.get("height", ""),  # type: ignore
        )
        document.add_predicate(
            predicate=document.namespace.hasWidth,  # type: ignore
            value=self.metadata.get("width", ""),  # type: ignore
        )
        document.add_predicate(
            predicate=document.namespace.hasFPS,  # type: ignore
            value=self.metadata.get("fps", ""),  # type: ignore
        )
        document.add_predicate(
            predicate=document.namespace.hasFileSize,  # type: ignore
            value=self.metadata.get("filesize", ""),  # type: ignore
        )
        document.add_predicate(
            predicate=document.namespace.hasExtension,  # type: ignore
            value=self.metadata.get("ext", ""),  # type: ignore
        )
        document.add_predicate(
            predicate=document.namespace.hasTranscript,  # type: ignore
            value=self.content,  # type: ignore
        )
        document.update_metadata("transcript", self.content)  # type: ignore
        # thumbnails – list of all available thumbnail urls
        document.add_predicate(
            predicate=document.namespace.hasFormat,  # type: ignore
            value=self.metadata.get("formats", ""),  # type: ignore
        )
        document.add_predicate(
            predicate=document.namespace.metadata,  # type: ignore
            value=self.metadata,  # type: ignore
        )

        self.info(
            msg=Event.Created.value,
            step=Event.Completed.value,
            document=document,
            size=document.size,
        )

        return facade


class WriteYoutubeDocument(StrategyWrite):
    def execute(self, caller: IWattleflow, facade: ITarget, *args, **kwargs) -> bool:
        self.debug(
            msg=Event.Execute.value,
            step=Event.Started.value,
            caller=caller,
            facade=facade,
            **kwargs,
        )

        Attribute.evaluate(caller=self, target=caller, expected_type=IPipeline)
        Attribute.mandatory(caller=self, name="repository", cls=IRepository, **kwargs)
        Attribute.mandatory(caller=self, name="processor", cls=IProcessor, **kwargs)

        document: YoutubeGraph = facade.request()  # type: ignore
        filename: str = document.get(URIRef("hasFilename"), document.identifier)  # type: ignore
        filename = Path(filename).with_suffix(".json")  # type: ignore

        if not document.size > 0:  # type: ignore
            self.warning(
                msg=Event.Execute.value,
                step=Event.Check.value,
                error="Graph’s feeling a bit empty today!",
                document=document,
                size=document.size,
                filename=filename,
            )
            return False

        # update the document metadata metadata ...
        document.update_metadata("stored_by", caller.name)
        document.update_metadata("stored_at", datetime.now())

        # Utilises driver to manage data persistance.
        output = self.repository.driver.write(  # type: ignore
            filename=filename,
            ftype=FileTypes.GRAPH,
            data=document.content,
        )  # type: ignore

        self.info(
            msg=Event.Created.value,
            step=Event.Completed.value,
            document=document,
            output=output,
            size=document.size,
        )

        return True
