import re
from types import NoneType
from typing import List, Optional
import json
from pathlib import Path

import dash_bootstrap_components as dbc
from dash import html
from loguru import logger

from podology.data.Episode import Episode
from podology.search.utils import format_time
from config import TRANSCRIPT_DIR


def highlight_to_html_elements(text):
    """
    Turn a string with 1 or more <span [...]>highlighted</span> parts into a list of
    Dash HTML elements, where the highlighted parts are wrapped in a Span element.
    """
    parts = re.split(r"(<span .*?>.*?</span>)", text)
    span_content = []

    for part in parts:
        if part.startswith("<span ") and part.endswith("</span>"):
            match = re.match(r"(<span .*?>)(.*)(</span>)", part)
            if match:
                opening_tag = match.group(1)
                opening_match = re.match(r'.*?="(.*?)"', opening_tag)
                classname = opening_match.group(1) if opening_match else ""
                text = match.group(2)
                span_content.append(
                    html.Span(
                        children=[text],
                        className=classname,
                    )
                )
        else:
            span_content.append(part)

    span_content.append(" ")

    return span_content


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

    def _chunked(
        self, min_words: int = 40, max_words: int = 100, overlap: float = 0.0
    ) -> list:
        """
        Return a list of chunks, each containing between min_words and max_words words.
        Overlap is a float (0.0–0.9) indicating the fraction of each chunk to overlap with the next.
        """
        segments = self.raw_dict["segments"]
        n_segments = len(segments)
        chunks = []
        idx = 0

        def count_words(text):
            return len(text.strip().split())

        while idx < n_segments:
            current_chunk = []
            current_word_count = 0
            chunk_start_idx = idx

            # Aggregate segments until min_words is reached, but do not exceed max_words
            while idx < n_segments and (
                current_word_count < min_words
                or (
                    current_word_count + count_words(segments[idx]["text"]) <= max_words
                )
            ):
                current_chunk.append(segments[idx])
                current_word_count += count_words(segments[idx]["text"])
                idx += 1

            chunk_start = current_chunk[0]["start"]
            chunk_end = current_chunk[-1]["end"]
            chunk_text = " ".join([s["text"] for s in current_chunk])
            chunks.append(
                {
                    "text": chunk_text,
                    "start": chunk_start,
                    "end": chunk_end,
                }
            )

            # Calculate overlap in words
            if overlap > 0.0 and len(current_chunk) > 1:
                overlap_words = int(current_word_count * overlap)
                if overlap_words > 0:
                    # Walk backwards from the end of the chunk to find where to restart
                    words_seen = 0
                    rewind_idx = len(current_chunk) - 1
                    while rewind_idx > 0 and words_seen < overlap_words:
                        words_seen += count_words(current_chunk[rewind_idx]["text"])
                        rewind_idx -= 1
                    next_start_idx = chunk_start_idx + rewind_idx + 1
                    # Only continue if enough segments remain for a new chunk
                    if (
                        next_start_idx >= n_segments
                        or next_start_idx == chunk_start_idx
                    ):
                        break
                    idx = next_start_idx
                else:
                    break  # No overlap, so we're done

            while len(chunks) > 1 and chunks[-2]["end"] == chunks[-1]["end"]:
                chunks.pop(-1)

        return chunks

    def words(self, regularize: bool = False) -> list[tuple[str, float]]:
        """Return a list of all words and their start times.

        Args:
            regularized (bool): lowercase words and remove punctuation from start
                and end (not apostrophes like "we're").

        Returns:
            list[tuple[str,float]]: A list of word--time tuples.
        """
        words = []

        segmentlist = [i["words"] for i in self.raw_dict["segments"]]
        for wordlist in segmentlist:
            words.extend((i["word"], i["start"]) for i in wordlist)

        if regularize:
            words = [
                (re.sub(r"(^\W)|(\W$)|('\w\b)", "", word).lower(), start)
                for word, start in words
            ]

        return words

    def segments(
        self,
        episode_attrs: list | str = [],
        segment_attrs: list | str = [],
        diarize: bool = False,
    ) -> list[dict]:
        """Return the transcript as a dict.

        Use the desired level of partitioning (segments, chunks, diarization) and
        metadata (segment/chunk and episode-level) to return a list of dicts.

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
        if diarize:
            segments = self._diarized()
        else:
            segments = self.raw_dict["segments"].copy()

        for source_turn in segments:
            # Copy episode metadata from the object to each turn:
            turn = {i: getattr(self, i) for i in episode_attrs}

            # Copy transcript metadata from the source turn to each turn:
            turn.update({k: source_turn.get(k) for k in segment_attrs})

            out.append(turn)

        return out

    def chunks(
        self,
        episode_attrs: list | str = [],
        chunk_attrs: list | str = [],
        min_words: int = 40,
        max_words: int = 100,
        overlap: float = 0.0,
    ) -> list[dict]:
        """Return the transcript as a list of chunks.

        This form sets a min and max chunk size in words. Chunks are grown by segments
        until they reach max_words. Each chunk can contain chunk-level and/or episode-level
        metadata.

        Args:
            episode_attrs (list | str, optional): List of metadata fields about the episode
                to include. Defaults to [].
            chunk_attrs (list | str, optional): List of metadata fields about each chunk to
                include. Defaults to [].

        Returns:
            list[dict]: List of chunks with the specified metadata.
        """
        episode_attrs = (
            [episode_attrs] if isinstance(episode_attrs, str) else episode_attrs
        )
        chunk_attrs = [chunk_attrs] if isinstance(chunk_attrs, str) else chunk_attrs
        if "text" not in chunk_attrs:
            chunk_attrs.append("text")

        out = []
        chunks = self._chunked(
            min_words=min_words, max_words=max_words, overlap=overlap
        )

        for source_chunk in chunks:
            # Copy episode metadata from the object to each chunk:
            chunk = {i: getattr(self, i) for i in episode_attrs}

            # Copy transcript metadata from the source chunk to each chunk:
            chunk.update({k: source_chunk.get(k) for k in chunk_attrs})

            out.append(chunk)

        return out

    def _highlight_text(self, text, re_pattern_colorid):
        """Apply highlighting to text based on term patterns."""
        if not re_pattern_colorid:
            return text
        for pattern, colorid in re_pattern_colorid.items():
            fmt_str = f'<span class="half-circle-highlight term-color-{colorid} highlight-color-{colorid}">'
            text = pattern.sub(lambda m: f"{fmt_str}{m.group()}</span>", text)
        return text

    def _render_segment(self, seg, re_pattern_colorid=None):
        """Render a single segment as a span with data attributes."""
        text = self._highlight_text(seg["text"], re_pattern_colorid)
        return html.Span(
            highlight_to_html_elements(text),
            className="transcript-segment",
            **{
                "data-start": seg["start"],
                "data-end": seg["end"],
                "data-speaker": seg["speaker"],
            },
        )

    def _render_turn(self, speaker, start, segments, speaker_class):
        """Render a speaker turn with header and body."""
        turn_header = dbc.Row(
            children=[
                dbc.Col(
                    [html.B([speaker + ":"])],
                    className="text-start text-bf",
                    width=6,
                ),
                dbc.Col(
                    [format_time(start)],
                    className="text-end text-secondary",
                    width=6,
                ),
            ],
            className="mt-2",
        )
        turn_body = html.Div(segments, className=speaker_class)
        return [turn_header, turn_body]

    def to_html(
        self, termtuples: List[tuple] | NoneType = None, diarized: bool = False
    ) -> list:
        """HTML representation of the transcript, semantically structured."""

        def speaker_class(speaker):
            return f"speaker-{speaker[-2:]}"

        # Compile search term patterns for case-insensitive matching
        re_pattern_colorid = None
        if termtuples:
            re_pattern_colorid = {
                re.compile(rf"\b{term}\b", re.IGNORECASE): colorid
                for term, colorid in termtuples
            }

        turns = []
        if diarized:
            # Group by speaker turns, but render each segment as a span
            diarized_turns = self._diarized()
            # Map each diarized turn to its original segments
            all_segments = self.raw_dict["segments"]
            for turn in diarized_turns:
                # Find all segments in this turn
                segs_in_turn = [
                    seg
                    for seg in all_segments
                    if seg["speaker"] == turn["speaker"]
                    and seg["start"] >= turn["start"]
                    and seg["end"] <= turn["end"]
                ]
                segment_spans = [
                    self._render_segment(seg, re_pattern_colorid)
                    for seg in segs_in_turn
                ]
                turns.extend(
                    self._render_turn(
                        turn["speaker"],
                        turn["start"],
                        segment_spans,
                        speaker_class(turn["speaker"]),
                    )
                )
        else:
            # Not diarized: render each segment as its own turn
            for seg in self.raw_dict["segments"]:
                segment_span = self._render_segment(seg, re_pattern_colorid)
                turns.extend(
                    self._render_turn(
                        seg["speaker"],
                        seg["start"],
                        [segment_span],
                        speaker_class(seg["speaker"]),
                    )
                )
        return turns
