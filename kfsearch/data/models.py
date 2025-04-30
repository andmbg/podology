import re
import json
from dataclasses import dataclass, field
from pathlib import Path
from types import NoneType
from typing import List
from loguru import logger

import requests
import dash_bootstrap_components as dbc
from dash import html

from kfsearch.data.utils import episode_hash
from kfsearch.data.connectors.base import Connector
from kfsearch.data.transcribers.base import Transcriber
from kfsearch.search.search_classes import highlight_to_html_elements
from kfsearch.search.utils import format_time
from kfsearch.config import EPISODE_STORE_PATH


@dataclass
class Episode:
    """
    Represent an episode of a podcast with a URL to the audio file.
    """

    eid: str | NoneType = field(default=None, init=False)
    store: "EpisodeStore"
    audio_url: str
    title: str = None
    pub_date: str = None
    description: str = None
    duration: str = None
    audio_path: str = None
    transcript_path: str = None
    wordcloud_path: str = None
    num_speakers: int = 2  # TODO: make settable by user

    def __post_init__(self):
        # Generate a 5-character alphanumeric hash from the URL
        self.eid = episode_hash(self.audio_url.encode())

        # Use file name stem for audio and transcript files
        name = self.audio_url.split("/")[-1].split(".")[0][:50]

        # If a transcript file already exists, set its name as attribute:
        transcript_path = self.store.transcripts_dir() / f"{self.eid}.json"
        if transcript_path.exists():
            self.transcript_path = str(transcript_path)

        # If an audio file already exists, set its name as attribute:
        audio_path = self.store.audio_dir() / f"{self.eid}.mp3"
        if audio_path.exists():
            self.audio_path = str(audio_path)
        
        # If a word cloud file already exists, set its name as attribute:
        wordcloud_path = self.store.wordclouds_dir() / f"{self.eid}.png"
        if wordcloud_path.exists():
            self.wordcloud_path = str(wordcloud_path)

        # Add the episode to the store, log if already present
        self.store.add(self)

    def __repr__(self):
        out = f"Episode (id '{self.eid}')\n"
        out += f"  Store: {self.store.name or '---'}\n"
        out += f"  Title: {self.title or '---'}\n"
        out += f"  Audio: {self.audio_path or '---'}\n"
        out += f"  TrScr: {self.transcript_path or '---'}\n"
        out += f"  URL:   {self.audio_url}\n"
        out += f"  Date:  {self.pub_date or '---'}\n"
        return out

    def transcribe(self):
        """
        - Check if a transcript exists and abort if so.
        - Let the transcriber use either the audio URL or the local audio file,
          depending on the transcriber type.
        """
        if self.transcript_path:
            logger.debug(f"Transcript for episode '{self.eid}' already exists.")
            return

        if not self.store.transcriber:
            logger.error(f"No Transcriber attached to this EpisodeStore.")
            return

        script_filename = (
            self.store.transcripts_dir() / f"{self.eid}.json"
        )

        # Get dict of the transcript from the transcriber:
        transcript: dict = self.store.transcriber.transcribe(self)

        with open(script_filename, "w") as file:
            json.dump(transcript, file, indent=4, ensure_ascii=False)

        self.transcript_path = script_filename

    def get_transcript(self) -> dict:
        """
        Load the transcript from the transcript directory if it exists.
        Return it as a dict.
        """
        if self.transcript_path and Path(self.transcript_path).exists():
            with open(self.transcript_path, "r") as file:
                return json.load(file)
        else:
            logger.debug(f"No transcript for episode '{self.eid}' found.")
            return {}

    def download_audio(self):
        """
        Download the audio file from the URL and save it to the audio directory of
        the containing EpisodeStore. Set self.audio_present to True and
        audio_filename to the audio filename.
        """
        if self.audio_path:
            logger.debug(f"Audio for episode '{self.eid}' already exists.")
            return
        else:
            response = requests.get(self.audio_url)
            filename = f"{self.eid or 'audio'}.mp3"

            with open(self.store.audio_dir() / filename, "wb") as file:
                file.write(response.content)

            self.audio_path = filename


class UniqueEpisodeError(Exception):
    pass


@dataclass
class EpisodeStore:
    """
    Manage episodes and their transcripts by setting storage paths and providing
    methods to add, remove, and get episodes.
    """
    name: str
    connector: Connector = None
    transcriber: Transcriber = None
    _episodes: list[Episode] = field(default_factory=list)

    # The _urls attribute is used to check for uniqueness.
    _urls: list[str] = field(default_factory=list)

    def __post_init__(self):
        # set paths to store directory
        self.path = EPISODE_STORE_PATH / self.name
        self._audio_path = self.path / "audio"
        self._transcripts_dir = self.path / "transcripts"
        self._wordclouds_dir = self.path / "stats" / "wordclouds"

        # Initialize the Store's _urls attribute with each Episode's audiofile_location;
        self._urls = [episode.audio_url for episode in self._episodes]

        # Create the directories for audio and transcripts if they don't exist
        self._audio_path.mkdir(parents=True, exist_ok=True)
        self._transcripts_dir.mkdir(parents=True, exist_ok=True)

        # Load episodes from JSON file if it exists
        json_file = EPISODE_STORE_PATH / self.name / f"{self.name}.json"
        if json_file.exists():
            with open(json_file, "r") as file:
                data = json.load(file)
                for ep_data in data:
                    Episode(
                        store=self,
                        audio_url=ep_data["audio_url"],
                        title=ep_data["title"],
                        pub_date=ep_data.get("pub_date"),
                        duration=ep_data.get("duration"),
                        description=ep_data.get("description"),
                    )

    def set_connector(self, connector: Connector):
        self.connector = connector
        self.connector.store = self
        self.connector.rss_file = self.path / "rss.xml"

    def set_transcriber(self, transcriber: Transcriber):
        self.transcriber = transcriber
        self.transcriber.store = self

    def populate(self):
        if self.connector:
            self.connector.populate_store()


    def to_json(self):
        """
        Store the metadata of the episodes in a JSON file, basically to reconstruct the
        store from a previous state and spare building it from the RSS every time.
        """
        json_file = self.path / f"{self.name}.json"
        data = [
            {
                "eid": episode.eid,
                "audio_url": episode.audio_url,
                "title": episode.title,
                "pub_date": episode.pub_date,
                "description": episode.description,
                "duration": episode.duration,
                "num_speakers": episode.num_speakers,
            }
            for episode in self._episodes
        ]

        with open(json_file, "w") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)

    def __repr__(self):
        out = f"EpisodeStore \"{self.name}\" ({len(self._episodes)} entries)\n"

        if self.connector:
            out += (
                "Metadata Connector: "
                f"{self.connector.__class__.__name__} "
                f"({self.connector.resource})\n"
            )
        else:
            out += "Metadata Connector: None\n"

        if self.transcriber:
            out += f"Transcriber: {self.transcriber.__class__.__name__}\n"
        else:
            out += "Transcriber: None\n"

        out += "\nEpisodes:\n"

        if len(self._episodes) < 8:
            for i, episode in enumerate(self._episodes):
                out += f'  {i}: {episode.eid} "{episode.title}" \n'
        else:
            for i, episode in list(enumerate(self._episodes))[:3]:
                out += f'  {i}: {episode.eid} "{episode.title}" \n'
            out += "  ...\n"
            for i, episode in list(enumerate(self._episodes))[-3:]:
                out += f'  {i}: {episode.eid} "{episode.title}" \n'

        return out

    def add(self, episode: Episode):
        """
        Enforce unique episodes when adding new ones.
        """
        if episode.audio_url not in self._urls:
            # Update store:
            self._episodes.append(episode)
            self._urls.append(episode.audio_url)

            # Update episode:
            episode._store = self

        else:
            raise UniqueEpisodeError(
                f"Episode with URL '{episode.audio_url}' already exists in store."
            )

    def remove(self, episode: Episode):
        if episode.audio_url in self._urls:
            self._urls.remove(episode.audio_url)
            self._episodes.remove(episode)

    def get_episode(self, eid: str):
        for episode in self._episodes:
            if episode.eid == eid:
                return episode
    
    def __getitem__(self, episode_id) -> Episode:
        # Retrieve the episode by its ID
        return self.get_episode(episode_id)

    def __iter__(self):
        return iter(self._episodes)

    def __len__(self):
        return len(self._episodes)

    def episodes(self, script: bool = None, audio: bool = None):
        """
        Episode getter. Return all episodes or filter by them having audio or
        transcripts.
        """
        out = []

        for ep in self._episodes:
            if script is not None:
                if script and ep.transcript_path is None:
                    continue
                if not script and ep.transcript_path is not None:
                    continue
            if audio is not None:
                if audio and ep.audio_path is None:
                    continue
                if not audio and ep.audio_path is not None:
                    continue

            out.append(ep)

        return out

    def transcripts_dir(self):
        return self._transcripts_dir

    def audio_dir(self):
        return self._audio_path
    
    def wordclouds_dir(self):
        return self._wordclouds_dir

    def urls(self) -> list:
        return [i for i in self._urls]

    def __iter__(self):
        return iter(self._episodes)

    def __len__(self):
        return len(self._episodes)


class DiarizedTranscript:
    """
    Takes an episode transcript and provides
    - a method that returns a plain JSON diarized transcript
    - a method that returns the HTML representation of the transcript that we
      use in the transcripts tab
    """
    def __init__(self, episode: Episode):
        self.eid = episode.eid
        self.episode_store = episode.store

        # Auto-filled from the episode store:
        self.title = self.episode_store.get_episode(self.eid).title
        self.pub_date = self.episode_store.get_episode(self.eid).pub_date
        self.description = self.episode_store.get_episode(self.eid).description
        self.audio_url = self.episode_store.get_episode(self.eid).audio_url
        self.duration = self.episode_store.get_episode(self.eid).duration

        # The meat of the class - the diarized transcript:
        self.diarized_script = self._diarize_script()

    def _diarize_script(self) -> list:
        """
        Build json representation of the diarized transcript and store it in the object.
        Episode metadata are stored at the object level, so if we need a transcript with, say, date,
        we have a dedicated output method.
        """

        episode = self.episode_store.get_episode(self.eid)
        segments = episode.get_transcript()["segments"]

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
        episode_metadata: list = None,
        transcript_metadata: list = None,
    ):
        """

        """
        episode_metadata = episode_metadata or []
        transcript_metadata = transcript_metadata or []
        episode_metadata = [episode_metadata] if isinstance(episode_metadata, str) else episode_metadata
        transcript_metadata = [transcript_metadata] if isinstance(transcript_metadata, str) else transcript_metadata

        out = []

        for source_turn in self.diarized_script:
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
        segments = self.diarized_script
        turns = []
        while segments:
            seg = segments.pop(0)
            text = " ".join(seg["text"])

            # TODO: First replacing strings and then replacing those with elements
            # is cumbersome. We have noticeable lag here.
            # Highlighting to do?
            if re_pattern_colorid:
                for pattern, colorid in re_pattern_colorid.items():
                    fmt_str = f'<span class="half-circle-highlight term-color-{colorid}">'
                    text = pattern.sub(lambda m: f"{fmt_str}{m.group()}</span>", text)

            highlighted_turn = highlight_to_html_elements(text)


            turn_header = dbc.Row(
                children=[
                    dbc.Col([html.B([seg["speaker"] + ":"])], className="text-start text-bf", width=6),
                    dbc.Col([format_time(seg["start"])], className="text-end text-secondary", width=6),
                ],
                className="mt-2"
            )
            turn_body = dbc.Row(
                children=[
                    html.Div([highlighted_turn], className=speaker_class(seg["speaker"])),
                ]
            )

            turns.append(turn_header)
            turns.append(turn_body)

        return turns