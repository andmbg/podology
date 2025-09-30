import time

from loguru import logger

from ...data.Episode import Status
from ...data.transcribers.base import Transcriber
from ...stats.preparation import post_process_pipeline
from ...data.transcribers.whisperx import WhisperXTranscriber
from ....config import TRANSCRIBER_ARGS


def transcription_worker(eid: str, timeout: int = 28800, interval: int = 5):
    """Worker function for transcription jobs.

    Runs in a background worker process, typically managed by RQ (Redis Queue).
    Instantiates a transcriber object of the class specified in config.py,
    which is interchangeable to use different transcription services, models, or APIs.
    The transcriber object handles sending the audio file to the transcription service,
    polling for the job's completion, saving the resulting transcript to disk, and
    post-processing the transcript (e.g., generating stats, enqueueing scrollvid worker).
    """
    from podology.data.EpisodeStore import EpisodeStore
    
    episode_store = EpisodeStore()
    episode = episode_store[eid]
    
    try:
        transcriber: Transcriber = WhisperXTranscriber(**TRANSCRIBER_ARGS)
    except Exception as e:
        episode.transcript.status = Status.ERROR
        episode_store.add_or_update(episode)
        raise

    audio_path = episode_store.audio_dir / f"{episode.eid}.mp3"

    # 1. Download audio if not already done
    episode_store.ensure_audio(episode)
    if episode.audio.status != Status.DONE:
        logger.error(f"{eid}: Failed to download audio.")
        return

    # 2. Submit job to API
    # The transcriber object here is of the kind that we select in config.py; it's
    # interchangeable, so the API doing the work is abstracted away.
    if episode.transcript.status == Status.DONE:
        logger.info(f"{eid}: Transcript already exists, skipping transcription.")
        return

    logger.debug(f"{eid}: Submitting transcription job for episode")
    try:
        transcriber.submit_job(audio_path=audio_path, job_id=eid)
        episode.transcript.status = Status.DONE
    except Exception as e:
        logger.error(f"{eid}: Transcription job failed: {e}")
        episode.transcript.status = Status.ERROR
        episode_store.add_or_update(episode)
        return

    post_process_pipeline(episode_store, [episode])
    episode_store.add_or_update(episode)
    logger.debug(f"{eid}: Transcription job completed successfully.")
    episode_store.add_or_update(episode)
