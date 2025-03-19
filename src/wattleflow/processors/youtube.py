# Module Name: core/processors/youtube.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains youtube transcript processor class.

import re
from typing import Generator
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    CouldNotRetrieveTranscript,
    NotTranslatable,
    NoTranscriptFound,
    TranscriptsDisabled,
)
from wattleflow.concrete import DocumentFacade, GenericProcessor
from wattleflow.concrete.processor import T

# --------------------------------------------------------------------------- #
# IMPORTANT:
# This test case requires the youtube-transcript-api library.
# Ensure you have it installed using:
#   pip install youtube-transcript-api
# The library is used to fetch transcripts (subtitles) from YouTube videos.
# --------------------------------------------------------------------------- #


class YoutubeTranscriptProcessor(GenericProcessor[DocumentFacade]):
    def __init__(
        self, strategy_audit, blackboard, pipelines, storage_path: str, videos: list
    ):
        super().__init__(strategy_audit, blackboard, pipelines)

        if not len(videos) > 0:
            raise ValueError("Missing youtube video list.")

        self._storage_path = storage_path
        self._videos = videos
        self._iterator = self.create_iterator()

    def __get_video_id(self, uri):
        match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", uri)
        return match.group(1) if match else None

    def get_transcript_document(self, video_id) -> T:
        try:
            content = YouTubeTranscriptApi.get_transcript(video_id)
            return self.blackboard.create(
                self,
                item=video_id,
                content=content,
            )
        # from youtube_transcript_api import _errors
        # print(dir(_errors))
        except CouldNotRetrieveTranscript:
            return "Could not retrieve the transcript for this video."
        except NotTranslatable:
            return "This video can not be translated."
        except TranscriptsDisabled:
            return "Transcripts are disabled for this video."
        except NoTranscriptFound:
            return "No transcript is available for this video."
        except Exception as e:
            raise ConnectionError(e)

    def create_iterator(self) -> Generator[T, None, None]:
        for url in self._videos:
            video_id = self.__get_video_id(url)
            if video_id:
                yield self.get_transcript_document(video_id)
