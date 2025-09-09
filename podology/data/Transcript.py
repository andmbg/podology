import re
from types import NoneType
from typing import List, Optional
import json
from pathlib import Path

import dash_bootstrap_components as dbc
from dash import html
from loguru import logger

from podology.data.Episode import Episode
from podology.search.search_classes import highlight_to_html_elements
from podology.search.utils import format_time
from config import TRANSCRIPT_DIR


class Transcript:
    """
    Represents an Episode's transcript. The Episode object only contains a reference to
    the raw transcript file. These here methods deliver the transcript in the desired
    formats:

    - diarized transcript: dict with turns blocked by speaker
    - the HTML representation of the diarized transcript for use in the transcripts tab
    """

    def __init__(self, episode: Episode):
        """Initialize the Transcript object.

        Copy all episode attributes to the Transcript object. Catalog available
        episode and segment attributes.

        - episode_attrs: list of episode attributes available to self.segment()
        - segment_attrs: list of segment attributes available to self.segment()

        Args:
            episode (Episode): The episode object containing metadata and transcript
            information.

        Raises:
            ValueError: If the transcript file is not available.
        """
        episode_attrs = list(episode.__dataclass_fields__.keys())
        self.episode_attrs = episode_attrs
        for attr in episode_attrs:
            self.__setattr__(attr, getattr(episode, attr))

        if episode.transcript.status:
            self.path: Path = TRANSCRIPT_DIR / f"{self.__getattribute__('eid')}.json"
        if self.path is None or not self.path.exists():
            raise ValueError(
                f"Transcript not available for episode {self.__getattribute__('eid')}."
            )
        self.raw_dict = json.load(open(self.path, "r"))
        self.segment_attrs = set()
        for seg in self.raw_dict["segments"]:
            this_attrs = set(seg.keys())
            self.segment_attrs = self.segment_attrs.union(this_attrs)
        self.segment_attrs = list(self.segment_attrs)

    def _diarized(self) -> list:
        """
        Return a JSON representation of the diarized transcript.
        """
        segments = self.raw_dict["segments"].copy()
        turns = []

        while segments:
            this_segment = segments.pop(0)
            current_speaker = this_segment["speaker"]
            start_time = this_segment["start"]
            end_time = this_segment["end"]
            texts = [this_segment["text"].strip()]

            while segments and segments[0]["speaker"] == current_speaker:
                next_segment = segments.pop(0)
                end_time = next_segment["end"]
                texts.append(next_segment["text"].strip())

            turn = {
                "speaker": current_speaker,
                "start": start_time,
                "end": end_time,
                "text": " ".join(texts),
            }
            turns.append(turn)

        return turns

    def segments(
        self,
        episode_attrs: list | str = [],
        segment_attrs: list | str = [],
        diarized: bool = False,
    ) -> list[dict]:
        """Return the transcript in JSON format, with the selected level of metadata



        :param episode_metadata: List of metadata fields about the episode to include.
        :param transcript_metadata: List of metadata fields about each turn to include.
        """
        episode_attrs = (
            [episode_attrs] if isinstance(episode_attrs, str) else episode_attrs
        )
        segment_attrs = (
            [segment_attrs] if isinstance(segment_attrs, str) else segment_attrs
        )

        if "text" not in segment_attrs:
            segment_attrs.append("text")

        out = []
        segments = self._diarized() if diarized else self.raw_dict["segments"].copy()

        for source_turn in segments:
            # Copy episode metadata from the object to each turn:
            turn = {i: getattr(self, i) for i in episode_attrs}

            # Copy transcript metadata from the source turn to each turn:
            turn.update({k: source_turn.get(k) for k in segment_attrs})

            out.append(turn)

        return out

    def to_html(
        self, termtuples: List[tuple] | NoneType = None, diarized: bool = False
    ) -> list:
        """HTML representation of the transcript.

        Args:
            termtuples (List[tuple] | NoneType, optional): List of search terms
              to highlight and the color ID for each. Defaults to None.
            diarized (bool, optional): Diarize the transcript before returning.
              Defaults to False.

        Returns:
            list: list of HTML elements representing the transcript.
        """

        # Deprecate at some point, as it's STT API dependent:
        def speaker_class(speaker):
            """
            Map speaker to a CSS class for transcript display.
            """
            return f"speaker-{speaker[-2:]}"

        # Compile search term patterns for case-insensitive matching
        if termtuples:
            re_pattern_colorid = {}
            for term, colorid in termtuples:
                term_re = rf"\b{term}\b"
                pattern = re.compile(term_re, re.IGNORECASE)
                re_pattern_colorid[pattern] = colorid
        else:
            re_pattern_colorid = None

        # Start iteration through transcript segments:
        segments = self._diarized() if diarized else self.raw_dict["segments"].copy()
        turns = []
        while segments:
            seg = segments.pop(0)
            text = seg["text"]

            # TODO: First replacing strings and then replacing those with elements
            # is cumbersome. We have noticeable lag here.
            # Highlighting to do?
            if re_pattern_colorid:
                for pattern, colorid in re_pattern_colorid.items():
                    fmt_str = f'<span class="half-circle-highlight term-color-{colorid} highlight-color-{colorid}">'
                    text = pattern.sub(lambda m: f"{fmt_str}{m.group()}</span>", text)

            highlighted_turn = highlight_to_html_elements(text)

            turn_header = dbc.Row(
                children=[
                    dbc.Col(
                        [html.B([seg["speaker"] + ":"])],
                        className="text-start text-bf",
                        width=6,
                    ),
                    dbc.Col(
                        [format_time(seg["start"])],
                        className="text-end text-secondary",
                        width=6,
                    ),
                ],
                className="mt-2",
            )
            turn_body = dbc.Row(
                children=[
                    html.Div(
                        [highlighted_turn], className=speaker_class(seg["speaker"])
                    ),
                ]
            )

            turns.append(turn_header)
            turns.append(turn_body)

        return turns
