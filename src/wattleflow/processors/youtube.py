# Module Name: core/processors/youtube.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains youtube transcript processor class.

import re
from typing import Generator, Optional
from logging import Handler, ERROR
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    CouldNotRetrieveTranscript,
    NotTranslatable,
    NoTranscriptFound,
    NoTranscriptAvailable,
    TranscriptsDisabled,
)
from wattleflow.core import T
from wattleflow.concrete import DocumentFacade, GenericProcessor
from wattleflow.constants import Event

# --------------------------------------------------------------------------- #
# IMPORTANT:
# This processor requires the youtube-transcript-api library.
# Ensure you have it installed using:
#   pip install youtube-transcript-api
# The library is used to fetch transcripts (subtitles) from YouTube videos.
# --------------------------------------------------------------------------- #


class TranscriptError(Exception):
    def __init__(self, reason, error):
        self.reason = reason
        self.error = error
        super().__init__(reason, error)


class YoutubeTranscriptProcessor(GenericProcessor[DocumentFacade]):
    def __init__(
        self,
        blackboard,
        pipelines,
        storage_path: str,
        videos: list,
        level: int = ERROR,
        handler: Optional[Handler] = None,
        **kwargs,
    ):
        GenericProcessor.__init__(
            self,
            blackboard=blackboard,
            pipelines=pipelines,
            level=level,
            handler=handler,
            allowed=["storage_path", "videos"],
            storage_path=storage_path,
            videos=videos,
        )

        self.debug(
            msg=Event.Initialised.value,
            storage_path=self.storage_path,
            videos=self.videos,
        )

        if not len(self.videos) > 0:
            error = "Missing youtube video list."
            self.warning(msg=error)
            raise ValueError(error)

    def __get_video_id(self, uri):
        match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", uri)

        self.debug(
            msg=Event.Retrieving.value,
            call="__get_video_id",
            uri=uri,
            match=match,
        )

        return match.group(1) if match else None

    def get_transcript_document(self, video_id) -> T:
        try:
            self.debug(
                msg=Event.Retrieving.value,
                call="get_transcript_document",
                video_id=video_id,
            )

            content = YouTubeTranscriptApi.get_transcript(video_id)

            if not len(content) > 0:
                self.warning(
                    msg="Video transcript is missing!",
                    size=len(content),
                )

            return self.blackboard.create(
                self,
                item=video_id,
                content=content,
            )

        except CouldNotRetrieveTranscript as e:
            raise TranscriptError(
                reason="Transcript can not be retrieved.", error=str(e)
            )
        except NotTranslatable as e:
            raise TranscriptError(
                reason="This video transcript can't be translated.", error=str(e)
            )
        except NoTranscriptFound as e:
            raise TranscriptError(
                reason="Transcript is not found for this video.", error=str(e)
            )
        except TranscriptsDisabled as e:
            raise TranscriptError(
                reason="Transcripts are disabled for this video.", error=str(e)
            )
        except NoTranscriptAvailable as e:
            raise TranscriptError(
                reason="No transcript is available for this video.", error=str(e)
            )
        except Exception as e:
            raise Exception(e)

    def create_iterator(self) -> Generator[T, None, None]:
        for url in self.videos:
            self.debug(msg=Event.Iterating.value, url=url)
            video_id = self.__get_video_id(url)
            try:
                if video_id:
                    self.info(
                        msg=Event.Iterating.value,
                        url=url,
                        id=video_id,
                    )
                    item = self.get_transcript_document(video_id)
                    yield item
                else:
                    self.warning(msg="No video_id is allocated.")
            except TranscriptError as e:
                self.critical(
                    msg=e.reason,
                    url=url,
                    error=e.error,
                )

            except Exception as e:
                self.critical(
                    msg=url,
                    error=str(e),
                    url=url,
                )
