"""
RSS Connector class
"""

from xml.etree import ElementTree
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field

import requests
from loguru import logger

from config import AUDIO_DIR, TRANSCRIPT_DIR, WORDCLOUD_DIR
from podology.data.connectors.base import Connector
from podology.data.Episode import Episode, AudioInfo, Status, TranscriptInfo
from podology.data.utils import episode_hash
from config import DATA_DIR, PROJECT_NAME


class RSSConnector(Connector):
    """
    Attaches to an EpisodeStore. Given a URL as its 'resource' attribute, downloads the
    RSS feed from the URL and saves it to a file in the store's data directory. Provides
    the populate_store method to extract episode metadata from the RSS feed and save it
    in the EpisodeStore JSON file.
    """

    def __init__(self, remote_resource: str):
        self.remote_resource: str = remote_resource
        self.local_rss_file: Path = DATA_DIR / PROJECT_NAME / f"{PROJECT_NAME}.rss"

    def fetch_episodes(self) -> list[Episode]:
        """
        Build a list of Episode data objects from the RSS feed to update the EpisodeStore.
        """
        rss_content = None
        try:
            response = requests.get(self.remote_resource, timeout=3)
            response.raise_for_status()
            rss_content = response.text
            # Save a local copy
            with open(self.local_rss_file, "w") as f:
                f.write(rss_content)

        except Exception as e:
            # If download fails, try to load the local file
            logger.info("RSS download failed, using local copy.")
            try:
                with open(self.local_rss_file, "r") as f:
                    rss_content = f.read()
            except Exception as local_e:
                raise RuntimeError(
                    f"Failed to fetch RSS from {self.remote_resource} ({e}) "
                    f"and failed to load local file {self.local_rss_file} ({local_e})"
                )

        return self._parse_rss(rss_content)

    def _parse_rss(self, rss_content: str) -> list[Episode]:
        """
        The arduous part of extracting XML data and dealing with varieties of form:
        """
        root = ElementTree.fromstring(rss_content)

        episodes = []

        for item in root.findall(".//item"):

            # Checking for empty values is the verbose part here:
            title_elem = item.find("title")
            if title_elem is None or title_elem.text is None:
                logger.error("No title found in item.")
                title = ""
            else:
                title = title_elem.text

            pub_date = item.find("pubDate")
            if pub_date is None or pub_date.text is None:
                logger.error("No publication date found in item.")
                pub_date = ""
            else:
                pub_date = datetime.strptime(
                    pub_date.text, "%a, %d %b %Y %H:%M:%S %z"
                ).strftime("%Y-%m-%d")

            description = item.find("description")
            if description is None or description.text is None:
                logger.error("No description found in item.")
                description = ""
            else:
                description = description.text

            url = item.find("enclosure")
            if url is None:
                logger.error("No URL found in item. Skipping.")
                continue
            else:
                url = url.attrib["url"]

            duration = item.find("{http://www.itunes.com/dtds/podcast-1.0.dtd}duration")
            if duration is None or duration.text is None:
                logger.error("No duration found in item.")
                duration = ""
            else:
                duration = duration.text

            eid = episode_hash(url.encode())

            # The distilled result:
            episode = Episode(
                eid=eid,
                url=url,
                title=title,
                pub_date=pub_date,
                description=description,
                duration=duration,
                audio=AudioInfo(status=Status.NOT_DONE),
                transcript=TranscriptInfo(
                    job_id=None,
                    queue_id=None,
                    status=Status.NOT_DONE,
                    wcstatus=Status.NOT_DONE,
                    scrollvid_status=Status.NOT_DONE,
                ),
            )

            episodes.append(episode)

        return episodes

    def _download_rss(self):
        """
        Download the RSS feed from the given URL or file path and save it to a temp file.
        """
        if self._is_url(self.remote_resource):
            response = requests.get(self.remote_resource, timeout=3)
            response.raise_for_status()
            logger.debug(f"RSS feed downloaded from {self.remote_resource}")

            with open(self.local_rss_file, "wb") as file:
                file.write(response.content)

            return

    def _rss_from_file(self):
        """
        If the RSS resource is not a URL, assume it's a local file path:
        """
        # Stated the project rss file as source: do nothing
        if self.remote_resource == DATA_DIR / PROJECT_NAME / f"{PROJECT_NAME}.rss":
            return

            logger.debug(f"Using local RSS file: {self.remote_resource}")
            return
        try:
            with open(Path(self.remote_resource), "r") as file:
                with open(self.local_rss_file, "wb") as out_file:
                    out_file.write(file.read().encode("utf-8"))

        except FileNotFoundError:
            logger.error(f"File not found: {self.remote_resource}")

            return

    def _is_url(self, resource: str) -> bool:
        return resource.startswith("http://") or resource.startswith("https://")

    def __repr__(self):
        out = super().__repr__()

        return out
