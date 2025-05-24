import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, List, Optional
from types import NoneType
import sqlite3

from loguru import logger
import requests

from config import DATA_DIR
from kfsearch.data.Episode import AudioInfo, Episode, Status, TranscriptInfo
from kfsearch.data.connectors.base import Connector, PublicEpisodeInfo
from kfsearch.data.UniqueEpisodeError import UniqueEpisodeError
from kfsearch.data.transcribers.base import Transcriber
from kfsearch.data.utils import episode_hash
from config import DB_PATH, AUDIO_DIR, TRANSCRIPT_DIR, WORDCLOUD_DIR


class EpisodeStore:
    """
    Manage episodes and their transcripts by setting storage paths and providing
    methods to add, remove, and get episodes.
    """
    def __init__(self, name: str):
        self.name = name
        self._ensure_table()
        self.len = self._len()

    def _connect(self):
        return sqlite3.connect(DB_PATH)

    def _ensure_table(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    eid TEXT PRIMARY KEY,
                    url TEXT UNIQUE,
                    title TEXT,
                    pub_date TEXT,
                    description TEXT,
                    duration TEXT,
                    transcript_path TEXT,
                    transcript_status TEXT,
                    transcript_wcpath TEXT,
                    transcript_wcstatus TEXT,
                    audio_path TEXT,
                    audio_status TEXT
                )
            """)
            conn.commit()

    def add_or_update(self, episode: Episode):
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO episodes (
                    eid, url, title, pub_date, description, duration,
                    transcript_path, transcript_status, transcript_wcpath, transcript_wcstatus,
                    audio_path, audio_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    episode.eid,
                    episode.url,
                    episode.title,
                    episode.pub_date,
                    episode.description,
                    episode.duration,
                    str(episode.transcript.path) if episode.transcript else None,
                    episode.transcript.status.name if episode.transcript else None,
                    str(episode.transcript.wcpath) if episode.transcript else None,
                    episode.transcript.wcstatus.name if episode.transcript else None,
                    str(episode.audio.path) if episode.audio else None,
                    episode.audio.status.name if episode.audio else None,
                )
            )
            conn.commit()
    
    def __getitem__(self, eid: str) -> Episode:
        with self._connect() as conn:
            cur = conn.execute("SELECT * FROM episodes WHERE eid = ?", (eid,))
            row = cur.fetchone()
            if row:
                return self._row_to_episode(row)

            raise KeyError(f"Episode with eid {eid} not found in the store.")
    
    def all(self) -> List[Episode]:
        with self._connect() as conn:
            cur = conn.execute("SELECT * FROM episodes")
            return [self._row_to_episode(row) for row in cur.fetchall()]
    
    def _len(self) -> int:
        with self._connect() as conn:
            cur = conn.execute("SELECT COUNT(*) FROM episodes")
            return cur.fetchone()[0]

    def __iter__(self) -> Iterator[Episode]:
        return iter(self.all())

    def delete(self, eid: str):
        with self._connect() as conn:
            conn.execute("DELETE FROM episodes WHERE eid = ?", (eid,))
            conn.commit()

    def _row_to_episode(self, row) -> Episode:
        # Adjust indices if you change the table schema!
        (
            eid, url, title, pub_date, description, duration,
            transcript_path, transcript_status, transcript_wcpath, transcript_wcstatus,
            audio_path, audio_status
        ) = row

        transcript = TranscriptInfo(
            path=Path(transcript_path) if transcript_path else Path(),
            status=Status[transcript_status] if transcript_status else Status.NOT_DONE,
            wcpath=Path(transcript_wcpath) if transcript_wcpath else Path(),
            wcstatus=Status[transcript_wcstatus] if transcript_wcstatus else Status.NOT_DONE,
        )

        audio = AudioInfo(
            path=Path(audio_path) if audio_path else Path(),
            status=Status[audio_status] if audio_status else Status.NOT_DONE,
        )

        return Episode(
            url=url,
            title=title,
            pub_date=pub_date,
            description=description,
            duration=duration,
        )
    
    def download_audio(self, episode: Episode):
        """
        Download the audio file from the episode's URL, save it to disk,
        update the episode's audio path and status, and persist to DB.
        """
        audio_path = AUDIO_DIR / f"{episode.eid}.mp3"

        if audio_path.exists():
            logger.debug(f"{episode.eid}: Audio for episode already exists at {audio_path}.")
            episode.audio.path = audio_path
            episode.audio.status = Status.DONE
        else:
            logger.info(f"{episode.eid}: Downloading audio from {episode.url}...")
            response = requests.get(episode.url, timeout=30)
            with open(audio_path, "wb") as file:
                file.write(response.content)
            episode.audio.path = audio_path
            episode.audio.status = Status.DONE

        # Persist changes to the database
        self.add_or_update(episode)
    
    def get_transcription(self, episode: Episode, transcriber=None):
        """
        Generate and save a transcript for the given episode using the provided transcriber.
        Updates the episode's transcript status and persists to DB.
        """
        if transcriber is None:
            raise ValueError("A transcriber must be provided.")

        transcript_path = episode.transcript.path
        transcript_data = transcriber.transcribe(episode.audio.path)

        # Save transcript to file
        with open(transcript_path, "w", encoding="utf-8") as f:
            json.dump(transcript_data, f, ensure_ascii=False, indent=4)

        # Update episode status
        episode.transcript.status = Status.DONE
        self.add_or_update(episode)

    def __repr__(self):
        out = f'EpisodeStore "{self.name}" ({self.len} entries)\n'
        return out
