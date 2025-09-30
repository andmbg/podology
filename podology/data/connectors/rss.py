"""
RSS Connector class
"""

from xml.etree import ElementTree
from datetime import datetime
from pathlib import Path

import requests
from loguru import logger

from ...data.connectors.base import Connector
from ...data.Episode import Episode, AudioInfo, Status, TranscriptInfo
from ...data.utils import episode_hash
from ....config import DATA_DIR, PROJECT_NAME, AUDIO_DIR, TRANSCRIPT_DIR, WORDCLOUD_DIR


class RSSConnector(Connector):
    """
    Attaches to an EpisodeStore. Given a URL as its 'resource' attribute, downloads the
    RSS feed from the URL and saves it to a file in the store's data directory. Provides
    the populate_store method to extract episode metadata from the RSS feed and save it
    in the EpisodeStore JSON file.
    """

    def __init__(self, remote_resource: str):
        self.remote_resource: str = remote_resource
        self.local_rss_file: Path = super().local_rss_file

    def fetch_episodes(self) -> list[Episode]:
        """
        Build a list of Episode data objects from the RSS feed to update the EpisodeStore.
        """
        logger.debug(f"Fetching episodes from RSS feed: {self.remote_resource}")
        if self._is_url(self.remote_resource):
            rss_content = self._download_rss(self.remote_resource)
        else:
            rss_content = self._read_rss_from_file(self.remote_resource)

        return self._parse_rss(rss_content)

    def _download_rss(self, url: str) -> str:
        """Download the RSS feed from the given URL

        ...and return its content as a string.
        """
        try:
            response = requests.get(url, timeout=3)
            response.raise_for_status()
            logger.debug(f"RSS feed downloaded from {url}")
            rss_content = response.text

        except Exception as e:
            logger.info(f"RSS download failed, falling back to local copy. {e}")
            rss_content = self._read_rss_from_local()

        return rss_content

    def _read_rss_from_file(self, path: str) -> str:
        """
        If the RSS resource is not a URL, assume it's a local file path:
        """
        # Stated the project rss file as source: do nothing
        try:
            with open(Path(self.remote_resource), "r") as file:
                rss_content = file.read()
        except FileNotFoundError as e:
            logger.error(f"RSS File not found, falling back to local copy. {e}")
            rss_content = self._read_rss_from_local()

        return rss_content

    def _read_rss_from_local(self) -> str:
        """
        Read the RSS feed from the local file.
        """
        try:
            with open(self.local_rss_file, "r") as file:
                rss_content = file.read()
        except FileNotFoundError:
            logger.error(f"Local RSS copy not found: {self.local_rss_file}")
            raise

        return rss_content

    def _is_url(self, resource: str) -> bool:
        return resource.startswith("http://") or resource.startswith("https://")

    def __repr__(self):
        out = super().__repr__()

        return out

    def _parse_rss(self, rss_content: str) -> list[Episode]:
        """Turn RSS data into an Episode object.

        The arduous part of extracting XML data and dealing with varieties of form.
        This code may see a bunch of amendments and case distinctions if it is used
        against different RSS feed formats.
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
                duration = 0.0
            else:
                duration = parse_duration(duration.text)

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
                    status=Status.NOT_DONE,
                    wcstatus=Status.NOT_DONE,
                    chunkstatus=Status.NOT_DONE,
                ),
            )

            episodes.append(episode)

        return episodes

def parse_duration(duration_str: str) -> float:
    """
    Parse a duration string (e.g. '1:30:00') into a float representing the
    total number of seconds.
    """
    parts = duration_str.split(":")
    if len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2])
    elif len(parts) == 2:
        hours = 0
        minutes = int(parts[0])
        seconds = int(parts[1])
    else:
        logger.error(f"Invalid duration format: {duration_str}")
        return 0.0

    return hours * 3600 + minutes * 60 + seconds
