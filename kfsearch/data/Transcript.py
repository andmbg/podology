import re
from types import NoneType
from typing import List, Optional
import json
from pathlib import Path

import dash_bootstrap_components as dbc
from dash import html

from kfsearch.data.Episode import Episode
from kfsearch.search.search_classes import highlight_to_html_elements
from kfsearch.search.utils import format_time
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
        self.eid = episode.eid
        if episode.transcript.status:
            self.path: Path = TRANSCRIPT_DIR / f"{self.eid}.json"
        self.status = episode.transcript.status

        if self.path is None or not self.path.exists():
            raise ValueError(f"Transcript not available for episode {self.eid}.")

        self.raw_dict = json.load(open(self.path, "r"))
    
    def segments(self) -> list:
        """
        Return the raw segments of the transcript, without timing or speaker information.
        """
        return self.raw_dict["segments"]

    def diarized(self) -> list:
        """
        Return a JSON representation of the diarized transcript.
        """
        segments = self.raw_dict["segments"]

        turns = []
        while segments:
            turn_segments = []
            this_speaker = segments[0]["speaker"]
            this_start = segments[0]["start"]

            while segments and segments[0]["speaker"] == this_speaker:
                # Highlight search terms in segment text
                text = segments.pop(0)["text"]
                turn_segments.append(text)

            turn = {
                "speaker": this_speaker,
                "start": this_start,
                "text": turn_segments,
            }
            turns.append(turn)

        return turns

    def to_json(
        self,
        episode_metadata: Optional[list] = None,
        transcript_metadata: Optional[list] = None,
    ) -> list[str]:
        """
        Return the transcript in JSON format, with the selected level of metadata.

        :param episode_metadata: List of metadata fields about the episode to include.
        :param transcript_metadata: List of metadata fields about each turn to include.
        """
        episode_metadata = episode_metadata or []
        transcript_metadata = transcript_metadata or []
        episode_metadata = (
            [episode_metadata]
            if isinstance(episode_metadata, str)
            else episode_metadata
        )
        transcript_metadata = (
            [transcript_metadata]
            if isinstance(transcript_metadata, str)
            else transcript_metadata
        )

        out = []

        for source_turn in self.diarized():
            # Copy episode metadata from the object to each turn:
            turn = {i: getattr(self, i) for i in episode_metadata}

            # Copy transcript metadata from the source turn to each turn:
            turn.update({k: source_turn.get(k) for k in transcript_metadata})

            # Finally: the text
            turn["text"] = " ".join(source_turn["text"])

            out.append(turn)

        return out

    def to_html(self, termtuples: List[tuple] | NoneType = None) -> list:

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
        segments = self.diarized()
        turns = []
        while segments:
            seg = segments.pop(0)
            text = " ".join(seg["text"])

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
