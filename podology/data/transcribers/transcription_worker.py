import time

from loguru import logger

from podology.data.Episode import Status
from podology.data.transcribers.base import Transcriber
from podology.search.setup_es import index_episode_worker
from podology.stats.preparation import post_process
from config import get_transcriber


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
    transcriber: Transcriber = get_transcriber()
    audio_path = episode_store.audio_dir / f"{episode.eid}.mp3"
    transcript_path = episode_store.transcript_dir / f"{episode.eid}.json"

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
    transcriber.submit_job(audio_path=audio_path, job_id=eid)
    episode.transcript.status = Status.PROCESSING

    episode_store.add_or_update(episode)

    # 3. Poll for completion, get download URL
    elapsed = 0
    
    while elapsed < timeout:
        status_dict = transcriber.get_status(eid)
        if status_dict["status"] == "done":
            break

        elif status_dict["status"] == "failed":
            logger.error(f"{eid}: Transcription job failed. Logs:")
            logger.error(status_dict.get("error_message", "No error details provided."))

            episode.transcript.status = Status.ERROR
            episode_store.add_or_update(episode)
            return

        else:
            logger.debug(f"{eid}: Transcription job still processing")

        elapsed += interval
        if elapsed >= timeout:
            raise TimeoutError(
                f"{eid}: Transcription job timed out after {timeout} seconds."
            )
        time.sleep(interval)

    # 4. Save the transcript to disk and update the episode
    transcriber.download_transcript(eid=eid, dest_path=transcript_path)

    episode.transcript.status = Status.DONE
    index_episode_worker(episode)
    post_process(episode_store, [episode])
    episode_store.add_or_update(episode)
    logger.debug(f"{eid}: Transcription job completed successfully.")
