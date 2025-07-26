import time
import sqlite3

from loguru import logger

from podology.data.Episode import Status
from config import RENDERER_CONFIG as RC
from podology.frontend.renderers.base import Renderer


def scrollvid_worker(eid: str, timeout: int = 28800, interval: int = 5):
    """Worker function for scroll video rendering jobs.
    """
    from podology.data.EpisodeStore import EpisodeStore
    episode_store = EpisodeStore()
    episode = episode_store[eid]
    renderer = Renderer(
        server_url=RC["server_url"],
        submit_endpoint=RC["submit_endpoint"],
        frame_step=RC.get("frame_step", 1000)
    )
    scrollvid_path = episode_store.scrollvid_dir / f"{episode.eid}.mp4"
    if not scrollvid_path.parent.exists():
        scrollvid_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Submit job to API
    if episode.transcript.scrollvid_status == Status.DONE:
        logger.info(f"{eid}: Scroll video already exists, skipping rendering.")
        return

    # Get named entity tokens from the database
    with sqlite3.connect(episode_store.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT timestamp, token FROM named_entity_tokens WHERE eid = ?",
            (episode.eid,)
        )
        naments = cursor.fetchall()

    job_id = eid
    logger.debug(f"{eid}: Submitting scroll video job for episode, job ID: {job_id}")
    renderer.submit_job(naments, job_id)
    episode.transcript.scrollvid_status = Status.PROCESSING
    
    episode_store.add_or_update(episode)

    # 2. Poll for completion, get download URL
    elapsed = 0
    while elapsed < timeout:
        status_dict = renderer.get_status(job_id)
        if status_dict["status"] == "done":
            break

        elif status_dict["status"] == "failed":
            logger.error(f"{eid}: Scroll video rendering job failed.")
            episode.transcript.scrollvid_status = Status.ERROR
            episode_store.add_or_update(episode)
            return

        elapsed += interval
        if elapsed >= timeout:
            raise TimeoutError(
                f"{eid}: Scroll video rendering job timed out after {timeout} seconds."
            )
        time.sleep(interval)
    
    # 3. Download & save the scroll video, update the episode
    renderer.download_video(job_id=job_id, dest_path=scrollvid_path)
