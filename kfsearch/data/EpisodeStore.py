import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from types import NoneType

from loguru import logger

from kfsearch.config import EPISODE_STORE_PATH
from kfsearch.data.Episode import AudioInfo, Episode, Status, TranscriptInfo
from kfsearch.data.connectors.base import Connector, PublicEpisodeInfo
from kfsearch.data.UniqueEpisodeError import UniqueEpisodeError
from kfsearch.data.transcribers.base import Transcriber
from kfsearch.data.utils import episode_hash


@dataclass
class EpisodeStore:
    """
    Manage episodes and their transcripts by setting storage paths and providing
    methods to add, remove, and get episodes.
    """

    name: str
    connector: Connector | NoneType = None
    transcriber: Optional[Transcriber] = None
    _episodes: list[Episode] = field(default_factory=list)

    def __post_init__(self):
        # set paths to store directory
        self.path = EPISODE_STORE_PATH / self.name
        self._json_path = self.path / f"{self.name}.json"
        self._audio_dir = self.path / "audio"
        self._transcripts_dir = self.path / "transcripts"
        self._wordclouds_dir = self.path / "stats" / "wordclouds"

        # Create the directories for assets if they don't exist:
        self._audio_dir.mkdir(parents=True, exist_ok=True)
        self._transcripts_dir.mkdir(parents=True, exist_ok=True)
        self._wordclouds_dir.mkdir(parents=True, exist_ok=True)

        self.populate_from_json()

        if self.connector:
            self.populate_from_connector()

    def populate_from_json(self):
        """
        If the JSON file for this Store exists already, load it and populate the
        self._episodes list with the contained data.
        """
        self._episodes = []

        if self._json_path.exists():
            with open(self._json_path, "r") as file:
                try:
                    data = json.load(file)
                except json.JSONDecodeError as e:
                    logger.error(f"Error decoding JSON file: {e}")
                    logger.error(
                        f"File: {self._json_path}; file length: {len(file.read())}"
                    )
                    return

            for ep_data in data:

                episode = Episode(
                    url=ep_data["url"],
                    store_path=self.path,
                    title=ep_data.get("title"),
                    pub_date=ep_data.get("pub_date"),
                    description=ep_data.get("description"),
                    duration=ep_data.get("duration"),
                )
                self._episodes.append(episode)

        else:
            logger.info(
                f"JSON file '{self._json_path}' does not exist. No episodes loaded."
            )

    def populate_from_connector(self):
        """
        Use the connector to populate the store with episodes. The connector is
        responsible for fetching the episode metadata from the resource and
        populating the store.
        """
        if self.connector is None:
            logger.info("No connector set. No episodes populated.")
            return

        pub_eps: list[PublicEpisodeInfo] = self.connector.fetch_episodes()

        n_new_eps = 0
        n_already_existing = 0

        for pub_ep in pub_eps:

            eid = episode_hash(pub_ep.url.encode())

            # Ignore this public episode if it already exists in the store:
            if eid in [ep.eid for ep in self._episodes]:
                n_already_existing += 1
                continue

            episode = Episode(
                store_path=self.path,
                url=pub_ep.url,
                title=pub_ep.title,
                pub_date=pub_ep.pub_date,
                description=pub_ep.description,
                duration=pub_ep.duration,
            )

            self._episodes.append(episode)
            n_new_eps += 1

        logger.info(f"Old episodes: {n_already_existing}; new episodes: {n_new_eps}.")

    def set_transcriber(self, transcriber: Transcriber):
        """
        Set the transcriber for the store. Currently, we could just set it during initialization,
        and do away with this method. However, in case we want to add the functionality of
        setting or changing the transcriber at runtime (it's thinkable), we keep it, even though
        right now, it doesn't add much functionality. Well, none, really.
        """
        self._transcriber = transcriber

    def to_json(self):
        """
        Store the metadata of the episodes in a JSON file, basically to reconstruct the
        store from a previous state and spare building it from source every time.
        """
        json_file = self.path / f"{self.name}.json"
        data = [
            {
                "eid": episode.eid,
                "url": episode.url,
                "title": episode.title,
                "pub_date": episode.pub_date,
                "description": episode.description,
                "duration": episode.duration,
                "audio": {
                    "path": str(episode.audio.path),
                },
                "transcript": {
                    "path": str(episode.transcript.path),
                    "wcpath": str(episode.transcript.wcpath),
                },
            }
            for episode in self._episodes
        ]

        with open(json_file, "w") as file:
            json.dump(data, file, indent=4)

    def __getitem__(self, eid: str) -> Episode:
        # Retrieve the episode by its ID
        for episode in self._episodes:
            if episode.eid == eid:
                return episode

        raise KeyError(f"Episode with ID '{eid}' not found in store.")

    def __setitem__(self, eid: str, episode: Episode):
        # Add or update an episode in the store
        for i, ep in enumerate(self._episodes):
            if ep.eid == eid:
                self._episodes[i] = episode
                return

        # If the episode is not found, add it to the store
        self._episodes.append(episode)

    def __iter__(self):
        return iter(self._episodes)

    def __len__(self):
        return len(self._episodes)

    def __repr__(self):
        out = f'EpisodeStore "{self.name}" ({len(self._episodes)} entries)\n'

        if self.connector:
            out += (
                "Metadata Connector: "
                f"{self.connector.__class__.__name__} "
                f"({self.connector.remote_resource})\n"
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
