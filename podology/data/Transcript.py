from collections import Counter
import re
from types import NoneType
from typing import List, Optional
import json
from pathlib import Path

import dash_bootstrap_components as dbc
from dash import html
from loguru import logger
import pandas as pd

from podology.data.Episode import Episode
from podology.search.utils import format_time
from config import TRANSCRIPT_DIR, EMBEDDER_ARGS


MIN_WORDS = EMBEDDER_ARGS["min_words"]
MAX_WORDS = EMBEDDER_ARGS["max_words"]
OVERLAP = EMBEDDER_ARGS["overlap"]


class Transcript:

    def __init__(self, episode: Episode):
        # Take over episode attributes:
        self.episode = episode

        if self.episode.transcript.status:
            path = TRANSCRIPT_DIR / f"{self.episode.eid}.json"
            if not path.exists():
                raise ValueError(
                    f"Transcript not available for episode {self.episode.eid}."
                )

            self.raw_segs = json.load(open(path, "r"))
            self._set_transcript_data()

    def _set_transcript_data(self):
        wordlist = []

        # set word and segment df from raw_segs:
        wid = 0
        for s, segment in enumerate(self.raw_segs.get("segments", [])):
            for w, word in enumerate(segment.get("words", [])):
                wordlist.append(
                    {
                        "wid": wid,
                        "word": word.get("word", ""),
                        "start": word.get("start", 0),
                        "end": word.get("end", 0),
                        "speaker": segment.get("speaker", ""),
                        "sid": s,
                    },
                )
                wid += 1

        # word_df: DataFrame containing word-level information
        self.word_df = pd.DataFrame(wordlist)[
            ["wid", "word", "start", "end"]
        ].set_index("wid")

        # segment_df: DataFrame containing segment-level information
        self.segment_df = (
            pd.DataFrame(wordlist)
            .reset_index()
            .groupby("sid")
            .agg(
                start=("index", "min"),
                end=("index", "max"),
                speaker=("speaker", _most_frequent),
            )
            # .reset_index()
            .rename(
                columns={
                    "start": "first_word_idx",
                    "end": "last_word_idx",
                }
            )
        )

        # chunk_df: DataFrame containing chunk-level information
        min_words = MIN_WORDS
        max_words = MAX_WORDS
        overlap = OVERLAP

        segments = self.raw_segs["segments"]
        n_segments = len(segments)
        chunks = []
        s_idx = 0
        chunk_word_idx_first = 0
        chunk_word_idx_last = -1

        while s_idx < n_segments:
            current_chunk = []
            current_chunk_wc = 0
            chunk_start_idx = s_idx

            # Concatenate segments; min_words is hard, max_words is soft:
            while s_idx < n_segments and (
                # currently too short (below min_words)
                current_chunk_wc < min_words
                or (
                    # would be in range with this seg (min < _ <= max_words)
                    current_chunk_wc + len(segments[s_idx]["words"])
                    <= max_words
                )
            ):
                current_seg_wc = len(segments[s_idx]["words"])
                current_chunk_wc += current_seg_wc
                current_chunk.append(current_seg_wc)
                s_idx += 1

            chunk_word_idx_first = chunk_word_idx_last + 1
            chunk_word_idx_last = chunk_word_idx_first + current_chunk_wc - 1

            chunks.append(
                {
                    "first_word_idx": chunk_word_idx_first,
                    "last_word_idx": chunk_word_idx_last,
                    "word_count": current_chunk_wc,
                }
            )

            # Calculate overlap in words
            if overlap > 0.0 and len(current_chunk) > 1:
                overlap_words = int(current_chunk_wc * overlap)
                if overlap_words > 0:
                    # Walk backwards from the end of the chunk to find where to restart
                    words_seen = 0
                    rewind_s_idx = len(current_chunk) - 1
                    while rewind_s_idx > 0 and words_seen < overlap_words:
                        words_seen += current_chunk[rewind_s_idx]
                        chunk_word_idx_last -= current_chunk[rewind_s_idx]
                        rewind_s_idx -= 1
                    next_start_idx = chunk_start_idx + rewind_s_idx + 1
                    # Only continue if enough segments remain for a new chunk
                    if (
                        next_start_idx >= n_segments
                        or next_start_idx == chunk_start_idx
                    ):
                        break
                    s_idx = next_start_idx
                else:
                    break  # No overlap, so we're done

            while (
                len(chunks) > 1
                and chunks[-2]["last_word_idx"] == chunks[-1]["last_word_idx"]
            ):
                chunks.pop(-1)

        chunks = [
            {
                "cid": i,
                "first_word_idx": chunk["first_word_idx"],
                "last_word_idx": chunk["last_word_idx"],
                "word_count": chunk["word_count"],
            }
            for i, chunk in enumerate(chunks)
        ]

        self.chunk_df = pd.DataFrame(chunks).set_index("cid")

        # Master Dataframe containing word- segment- and chunk level information:
        self.word_df["sid"] = None
        for sid, segment in self.segment_df.iterrows():
            mask = (self.word_df.index >= segment["first_word_idx"]) & (
                self.word_df.index <= segment["last_word_idx"]
            )
            self.word_df.loc[mask, "sid"] = int(sid)
        self.word_df["sid"] = self.word_df["sid"].astype(int)

        self.word_df["cid"] = None
        for cid, chunk in self.chunk_df.iterrows():
            mask = (self.word_df.index >= chunk["first_word_idx"]) & (
                self.word_df.index <= chunk["last_word_idx"]
            )
            self.word_df.loc[mask, "cid"] = int(cid)
        self.word_df["cid"] = self.word_df["cid"].astype(int)

    def words(self, regularize: bool = False) -> pd.DataFrame:
        """Return word df.

        Args:
            regularize (bool, optional): Whether to regularize the words. Defaults to False.
            segment_attrs (list | str, optional): Segment attributes to include. Defaults to [].

        Returns:
            list[dict]: List of words with desired metadata.
        """
        df = self.word_df.copy()[["word", "start"]]
        if regularize:
            df.word = df.word.str.lower().str.replace(r"(^\W)|(\W$)", "", regex=True)

        return df

    def segments(self, diarize: bool = False) -> pd.DataFrame:
        df = self.word_df.copy()[["word", "start", "sid"]]
        df = df.groupby("sid").agg(
            text=("word", lambda x: " ".join(x)),
            start=("start", "min"),
            end=("start", "max"),
        )
        df = df.join(self.segment_df[["speaker"]], how="left")

        if diarize:

            # Create a group identifier for consecutive same speakers
            df["turn_id"] = (df["speaker"] != df["speaker"].shift()).cumsum().sub(1)
            df = (
                df.groupby(["speaker", "turn_id"])
                .agg(
                    text=("text", " ".join),
                    start=("start", "min"),
                    end=("end", "max"),
                )
                .reset_index()
                # .drop(columns=["turn_id"])
                .sort_values(["start"])
            ).reset_index()[
                [
                    "text",
                    "start",
                    "end",
                    "speaker",
                    "turn_id",
                ]
            ]

        df["eid"] = self.episode.eid
        df["pub_date"] = self.episode.pub_date
        df["title"] = self.episode.title

        return df

    def chunks(self) -> pd.DataFrame:
        df = self.word_df.copy()[["word", "start", "end", "cid"]]
        df = df.groupby("cid").agg(
            text=("word", lambda x: " ".join(x)),
        )

        return df

    def to_html(
        self,
        termtuples: List[tuple] | NoneType = None,
    ) -> list:
        """HTML representation of the transcript, semantically structured."""

        def speaker_class(speaker):
            return f"speaker-{speaker[-2:]}"

        def _render_segment(seg, re_pattern_colorid=None) -> html.Span:
            """Render a single segment as a span with data attributes."""

            def _highlight_text(text, re_pattern_colorid) -> str:
                """Apply highlighting to text based on term patterns."""
                if not re_pattern_colorid:
                    return text

                for pattern, colorid in re_pattern_colorid.items():
                    fmt_str = f'<span class="half-circle-highlight term-color-{colorid} highlight-color-{colorid}">'
                    text = pattern.sub(lambda m: f"{fmt_str}{m.group()}</span>", text)
                return text

            def _highlight_to_html_elements(text) -> list[html.Span]:
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

            text = _highlight_text(seg["text"], re_pattern_colorid)
            return html.Span(
                _highlight_to_html_elements(text),
                className="transcript-segment",
                **{
                    "data-start": seg["start"],
                    "data-end": seg["end"],
                    "data-speaker": seg["speaker"],
                },
            )

        def _render_html_turn(
            speaker, start, segments, speaker_class
        ) -> tuple[dbc.Row, html.Div]:
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
            return (turn_header, turn_body)

        # Compile search term patterns for case-insensitive matching
        re_pattern_colorid = None
        if termtuples:
            re_pattern_colorid = {
                re.compile(rf"\b{term}\b", re.IGNORECASE): colorid
                for term, colorid in termtuples
            }

        turns = []
        # Group by speaker turns, but render each segment as a span
        diarized_turns = self.segments(diarize=True).to_dict(orient="records")
        # Map each diarized turn to its original segments
        all_segments = self.segments(diarize=False).to_dict(orient="records")
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
                _render_segment(seg, re_pattern_colorid) for seg in segs_in_turn
            ]
            turns.extend(
                list(
                    _render_html_turn(
                        turn["speaker"],
                        turn["start"],
                        segment_spans,
                        speaker_class(turn["speaker"]),
                    )
                )
            )

        return turns


def _most_frequent(lst: pd.Series) -> str | None:
    """Return the most frequent value in a list. If tied, return the earlier occurrence."""
    counter = Counter(lst)
    max_count = counter.most_common(1)[0][1]

    # Return first item with max count
    return next(item for item in lst if counter[item] == max_count)
