import json
from dataclasses import dataclass, field
from pathlib import Path
from loguru import logger

import requests

from kfsearch.data.utils import episode_hash
from kfsearch.data.speechtotext import LemonfoxTranscriber as Transcriber
from kfsearch.config import EPISODE_STORE_PATH


@dataclass
class Episode:
    """
    Represent an episode of a podcast with a URL to the audio file.
    """

    eid: str = field(default=None, init=False)
    store: "EpisodeStore"
    audio_url: str
    title: str = None
    pub_date: str = None
    description: str = None
    duration: str = None
    audio_filename: str = None
    transcript_path: str = None
    num_speakers: int = 2  # TODO: make settable by user
    transcript: dict = None

    def __post_init__(self):
        # Generate an 8-character alphanumeric hash from the URL
        self.eid = episode_hash(self.audio_url.encode())
        name = self.audio_url.split("/")[-1].split(".")[0][:50]

        # If a transcript file already exists, set its name as attribute:
        transcript_path = self.store.transcripts_dir() / f"{self.eid}_{name}.json"
        if transcript_path.exists():
            self.transcript_path = str(transcript_path)

        # If an audio file already exists, set its name as attribute:
        audio_path = self.store.audio_path() / f"{self.eid}_{name}.mp3"
        if audio_path.exists():
            self.audio_filename = str(audio_path)

        # Add the episode to the store, log if already present
        self.store.add(self)

    def __repr__(self):
        out = f"Episode (id '{self.eid}')\n"
        out += f"  Store: {self.store.name or '---'}\n"
        out += f"  Title: {self.title or '---'}\n"
        out += f"  Audio: {self.audio_filename or '---'}\n"
        out += f"  TrScr: {self.transcript_path or '---'}\n"
        out += f"  URL:   {self.audio_url}\n"
        out += f"  Date:  {self.pub_date or '---'}\n"
        return out

    def transcribe(self):
        """
        Check if a transcript exists and abort if so. Send the online mp3 behind
        self.url to an STT API for transcription. Download the transcript and save it
        to the transcript directory of the containing EpisodeStore. Set
        self.script_present to True and script_filename to the transcript filename.
        """
        if self.transcript_path:
            logger.debug(f"Transcript for episode '{self.eid}' already exists.")
            return
        else:
            transcriber = Transcriber()
            filename = self.audio_url.split("/")[-1].split(".")[0][:50]
            script_filename = (
                self.store.transcripts_dir() / f"{self.eid}_{filename}.json"
            )
            transcript: str = transcriber.transcribe(self.audio_url)

            with open(script_filename, "w") as file:
                json.dump(transcript, file, indent=4, ensure_ascii=False)

            self.transcript_path = script_filename

    def get_transcript(self):
        """
        Load the transcript from the transcript directory if it exists.
        Return it as a dict.
        """
        if self.transcript_path and Path(self.transcript_path).exists():
            with open(self.transcript_path, "r") as file:
                return json.load(file)
        else:
            logger.debug(f"No transcript for episode '{self.eid}' found.")
            return None

    def get_audio(self):
        """
        Download the audio file from the URL and save it to the audio directory of
        the containing EpisodeStore. Set self.audio_present to True and
        audio_filename to the audio filename.
        """
        if self.audio_filename:
            logger.debug(f"Audio for episode '{self.eid}' already exists.")
            return
        else:
            response = requests.get(self.audio_url)
            filename = f"{self.eid or 'audio'}.mp3"

            with open(self.store.audio_path() / filename, "wb") as file:
                file.write(response.content)

            self.audio_filename = filename

    def hit_context(self, s_id, highlight, context_length=300):
        """
        Return a context string for a hit in the transcript.
        """
        transcript = self.get_transcript()
        segment = transcript["segments"][s_id]


@dataclass
class EpisodeStore:
    """
    Manage episodes and their transcripts by setting storage paths and providing
    methods to add, remove, and get episodes.
    """

    name: str = "episode_store"
    path: Path = None
    _episodes: list[Episode] = field(default_factory=list)
    _urls: list[str] = field(default_factory=list)

    def __post_init__(self):
        # set paths to store directory
        self.path = EPISODE_STORE_PATH / self.name
        self._audio_path = self.path / "audio"
        self._transcripts_dir = self.path / "transcripts"

        # Initialize the Store's _urls attribute with each Episode's url;
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
                    episode = Episode(
                        store=self,
                        audio_url=ep_data["audio_url"],
                        title=ep_data["title"],
                        pub_date=ep_data.get("pub_date"),
                    )

    def to_json(self):
        """
        Store the metadata of the episodes in a JSON file, basically to reconstruct the
        store from a previous state and spare building it from the RSS every time.

        TODO: an update function that takes a newer RSS and only adds new episodes.
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
        out = f"EpisodeStore ({len(self._episodes)} entries)\n"
        out += f"   Name: {self.name}\n"
        out += f"  Audio: {self._audio_path}\n"
        out += f"  TrScr: {self._transcripts_dir}\n"
        out += "Episodes:\n"

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
            logger.info(
                f"Episode with URL '{episode.audio_url}' already exists in store."
            )

    def remove(self, episode: Episode):
        if episode.audio_url in self._urls:
            self._urls.remove(episode.audio_url)
            self._episodes.remove(episode)

    def get(self, url: str):
        for episode in self._episodes:
            if episode.audio_url == url:
                return episode

    def episodes(self, script: bool = None, audio: bool = None):

        out = []

        for ep in self._episodes:
            if script is not None:
                if script and ep.transcript_path is None:
                    continue
                if not script and ep.transcript_path is not None:
                    continue
            if audio is not None:
                if audio and ep.audio_filename is None:
                    continue
                if not audio and ep.audio_filename is not None:
                    continue
            out.append(ep)

        return out

    def transcripts_dir(self):
        return self._transcripts_dir

    def audio_path(self):
        return self._audio_path

    def urls(self) -> list:
        return [i for i in self._urls]

    def __iter__(self):
        return iter(self._episodes)

    def __len__(self):
        return len(self._episodes)
