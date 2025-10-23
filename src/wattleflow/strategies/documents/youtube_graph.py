# Module Name: youtube_graph.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This module provides strategies for generating and storing YouTubeGraph
# documents within the Wattleflow Workflow framework. It includes utilities
# to create, manage, and maintain structured representations of YouTube data.

"""
This module defines utilities for generating and storing YouTubeGraph
documents within the Wattleflow Workflow framework. It outlines strategies
to create, manage, and maintain YouTube-related graph data efficiently.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from wattleflow.core import (
    IPipeline,
    IProcessor,
    IRepository,
    ITarget,
    IWattleflow,
)
from wattleflow.concrete import (
    DocumentFacade,
    StrategyCreate,
    StrategyWrite,
)
from wattleflow.constants import Event
from wattleflow.drivers import FileTypes
from wattleflow.helpers import (
    Attribute,
)


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
    def execute(self, caller: IWattleflow, document: ITarget, *args, **kwargs) -> bool:
        self.debug(
            msg=Event.Execute.value,
            step=Event.Started.value,
            caller=caller,
            document=document,
            **kwargs,
        )

        Attribute.evaluate(caller=self, target=caller, expected_type=IPipeline)
        Attribute.mandatory(caller=self, name="repository", cls=IRepository, **kwargs)
        Attribute.mandatory(caller=self, name="processor", cls=IProcessor, **kwargs)

        # Utilises driver to manage data persistance.
        graph: YoutubeGraph = document.request()  # type: ignore
        filename: str = doc.metadata.get("id", str(doc.identifier))  # type: ignore
        filename = Path(filename).with_suffix(".json")  # type: ignore

        if not doc.size > 0:  # type: ignore
            self.warning(
                msg=Event.Execute.value,
                step=Event.Check.value,
                error="Graph’s feeling a bit empty today!",
                size=graph.size,
                filename=filename,
            )
            return False

        # update the document metadata metadata ...
        graph.update_metadata("stored_by", caller.name)
        graph.update_metadata("stored_at", datetime.now())

        output = self.repository.driver.write(  # type: ignore
            filename=filename,
            ftype=FileTypes.graph,
            document=graph,
        )  # type: ignore

        self.info(
            msg=Event.Created.value,
            step=Event.Completed.value,
            document=document,
            output=output,
            size=graph.size,
        )

        return True
