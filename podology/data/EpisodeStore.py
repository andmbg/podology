import secrets
from typing import Iterator
import sqlite3

from loguru import logger
import requests
from rq import Queue
from redis import Redis

from podology.data.Episode import AudioInfo, Episode, Status, TranscriptInfo
from config import (
    DB_PATH,
    DUMMY_AUDIO,
    AUDIO_DIR,
    TRANSCRIPT_DIR,
    WORDCLOUD_DIR,
    SCROLLVID_DIR,
)
from podology.data.transcribers.transcription_worker import transcription_worker
from podology.frontend.scrollvid_worker import scrollvid_worker


redis_conn = Redis()
transcription_q = Queue(connection=redis_conn, name="transcription")
scrollvid_q = Queue(connection=redis_conn, name="scrollvid")


class EpisodeStore:
    """
    Manage episodes and their transcripts by setting storage paths and providing
    methods to add, remove, and get episodes.
    """

    def __init__(self):
        self.db_path = DB_PATH
        self.audio_dir = AUDIO_DIR
        self.transcript_dir = TRANSCRIPT_DIR
        self.wordcloud_dir = WORDCLOUD_DIR
        self.dummy_audio = DUMMY_AUDIO
        self.scrollvid_dir = SCROLLVID_DIR
        self._ensure_table()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _ensure_table(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS episodes (
                    eid TEXT PRIMARY KEY,
                    url TEXT UNIQUE,
                    title TEXT,
                    pub_date TEXT,
                    description TEXT,
                    duration TEXT,
                    transcript_status TEXT,
                    transcript_job_id TEXT,
                    transcript_queue_id TEXT,
                    transcript_wcstatus TEXT,
                    transcript_scrollvid_status TEXT,
                    audio_status TEXT
                )
            """
            )
            conn.commit()

    def add_or_update(self, episode: Episode):
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO episodes (
                    eid, url, title, pub_date, description, duration,
                    transcript_status, transcript_job_id,
                    transcript_queue_id, transcript_wcstatus,
                    transcript_scrollvid_status, audio_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    episode.eid,
                    episode.url,
                    episode.title,
                    episode.pub_date,
                    episode.description,
                    episode.duration,
                    episode.transcript.status.name if episode.transcript else None,
                    episode.transcript.job_id if episode.transcript else None,
                    episode.transcript.queue_id if episode.transcript else None,
                    episode.transcript.wcstatus.name if episode.transcript else None,
                    (
                        episode.transcript.scrollvid_status.name
                        if episode.transcript
                        else None
                    ),
                    episode.audio.status.name if episode.audio else None,
                ),
            )
            conn.commit()

    def _row_to_episode(self, row) -> Episode:
        # Adjust indices if you change the table schema!
        (
            eid,
            url,
            title,
            pub_date,
            description,
            duration,
            transcript_status,
            transcript_job_id,
            transcript_queue_id,
            transcript_wcstatus,
            transcript_scrollvid_status,
            audio_status,
        ) = row

        transcript = TranscriptInfo(
            job_id=transcript_job_id if transcript_job_id else "",
            queue_id=transcript_queue_id if transcript_queue_id else "",
            status=Status[transcript_status] if transcript_status else Status.NOT_DONE,
            wcstatus=(
                Status[transcript_wcstatus] if transcript_wcstatus else Status.NOT_DONE
            ),
            scrollvid_status=(
                Status[transcript_scrollvid_status]
                if transcript_scrollvid_status
                else Status.NOT_DONE
            ),
        )

        audio = AudioInfo(
            status=Status[audio_status] if audio_status else Status.UNKNOWN,
        )

        return Episode(
            eid=eid,
            url=url,
            title=title,
            pub_date=pub_date,
            description=description,
            duration=duration,
            audio=audio,
            transcript=transcript,
        )

    def update_from_files(self):
        # Check if the audio, transcript, and wordcloud files exist:

        # Scan audio files
        for audio_file in self.audio_dir.glob("*.mp3"):
            eid = audio_file.stem
            try:
                episode = self[eid]
                episode.audio.status = Status.DONE
                self.add_or_update(episode)
            except KeyError:
                # Optionally: create new episode entry if not in DB
                pass

        # Scan transcript files
        for transcript_file in self.transcript_dir.glob("*.json"):
            eid = transcript_file.stem

            audio_exists = (
                Status.DONE
                if self.audio_dir.joinpath(f"{eid}.mp3").exists()
                else Status.NOT_DONE
            )
            transcript_exists = (
                Status.DONE
                if self.transcript_dir.joinpath(f"{eid}.json").exists()
                else Status.NOT_DONE
            )
            wordcloud_exists = (
                Status.DONE
                if self.wordcloud_dir.joinpath(f"{eid}.png").exists()
                else Status.NOT_DONE
            )

            audio_info = AudioInfo(status=audio_exists)

            transcript_info = TranscriptInfo(
                job_id=None,
                queue_id=None,
                status=transcript_exists,
                wcstatus=wordcloud_exists,
                scrollvid_status=Status.NOT_DONE,  # Placeholder, adjust if needed
            )

            try:
                episode = self[eid]
                episode.audio = audio_info
                episode.transcript = transcript_info
                self.add_or_update(episode)
            except KeyError:
                # Optionally: create new episode entry if not in DB
                pass

    def ensure_audio(self, episode: Episode):
        """
        Download the audio file from the episode's URL, save it to disk,
        update the episode's audio path and status, and persist to DB.
        Update status in the database before and after download.
        """
        audio_path = self.audio_dir / f"{episode.eid}.mp3"
        if audio_path.exists():
            logger.info(f"{episode.eid}: Audio already exists")
            episode.audio.status = Status.DONE
        else:
            if self.dummy_audio:
                logger.info(f"{episode.eid}: Creating dummy audio")
                with open(audio_path, "w") as file:
                    file.write("I am a dummy audio file.")
                episode.audio.status = Status.DONE

            else:
                episode.audio.status = Status.PROCESSING
                self.add_or_update(episode)
                logger.info(f"{episode.eid}: Downloading audio from {episode.url}")
                try:
                    response = requests.get(episode.url, timeout=30)
                    with open(audio_path, "wb") as file:
                        file.write(response.content)
                    episode.audio.status = Status.DONE
                except requests.RequestException as e:
                    episode.audio.status = Status.ERROR

        # Persist changes to the database
        self.add_or_update(episode)

    def enqueue_transcription_job(self, episode: Episode) -> str:
        """
        Enqueue a transcription job for the episode and update DB with queue job ID.
        """
        job = transcription_q.enqueue(
            transcription_worker,
            episode.eid,
            job_timeout=28800,
            job_id=generate_queue_id(),
            result_ttl=1,  # we just care about side effects, not the result
        )
        qid = job.id  # for clarity, cause "job-id" is taken in our app
        episode.transcript.status = Status.QUEUED
        episode.transcript.queue_id = qid  # This is the queue ID or qid
        self.add_or_update(episode)

        return qid

    def enqueue_scrollvid_job(self, episode: Episode) -> str:
        """
        Enqueue a scrollvid job for the episode and update DB with queue job ID.
        """
        job = scrollvid_q.enqueue(
            scrollvid_worker,
            episode.eid,
            job_timeout=28800,
            job_id=generate_queue_id(),
            result_ttl=1,
        )
        qid = job.id
        episode.transcript.scrollvid_status = Status.QUEUED_VID
        episode.transcript.queue_id = (
            qid if hasattr(episode.transcript, "scrollvid_queue_id") else None
        )
        self.add_or_update(episode)

        return qid

    def __getitem__(self, eid: str) -> Episode:
        with self._connect() as conn:
            cur = conn.execute("SELECT * FROM episodes WHERE eid = ?", (eid,))
            row = cur.fetchone()
            if row:
                return self._row_to_episode(row)

            raise KeyError(f"Episode with eid {eid} not found in the store.")

    def __iter__(self) -> Iterator[Episode]:
        with self._connect() as conn:
            cur = conn.execute("SELECT * FROM episodes")
            return iter([self._row_to_episode(row) for row in cur.fetchall()])


def generate_queue_id(length=8):
    return f"qid_{secrets.token_hex(length // 2)}"
