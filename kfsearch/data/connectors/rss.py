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
from kfsearch.data.connectors.base import Connector
from kfsearch.data.Episode import Episode, AudioInfo, Status, TranscriptInfo
from kfsearch.data.utils import episode_hash


@dataclass
class RSSConnector(Connector):
    """
    Attaches to an EpisodeStore. Given a URL as its 'resource' attribute, downloads the
    RSS feed from the URL and saves it to a file in the store's data directory. Provides
    the populate_store method to extract episode metadata from the RSS feed and save it
    in the EpisodeStore JSON file.
    """

    TEMPFILE: Path = field(default_factory=lambda: Path("/tmp/rss_feed.xml"))

    def __post_init__(self):
        pass

    def fetch_episodes(self) -> list[Episode]:
        """
        Build a list of Episode data objects from the RSS feed to update the EpisodeStore.
        """
        self._download_rss()

        # The arduous part of extracting XML data and dealing with varieties of form:
        tree = ElementTree.parse(self.TEMPFILE)
        root = tree.getroot()

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
                    pub_date.text,
                    "%a, %d %b %Y %H:%M:%S %z"
                ).strftime("%Y-%m-%d")

            description=item.find("description")
            if description is None or description.text is None:
                logger.error("No description found in item.")
                description = ""
            else:
                description = description.text

            url=item.find("enclosure")
            if url is None:
                logger.error("No URL found in item. Skipping.")
                continue
            else:
                url = url.attrib["url"]

            duration=item.find("{http://www.itunes.com/dtds/podcast-1.0.dtd}duration")
            if duration is None or duration.text is None:
                logger.error("No duration found in item.")
                duration = ""
            else:
                duration = duration.text

            eid = episode_hash(url.encode())

            # If the episode already exists, we skip it:
            if AUDIO_DIR.joinpath(f"{eid}.mp3").exists():
                logger.debug(f"Episode {eid} already exists. Skipping Connector import.")
                continue

            audio_info = AudioInfo(
                status=Status.NOT_DONE
            )

            transcript_info = TranscriptInfo(
                job_id="",
                status=Status.NOT_DONE,
                wcstatus=Status.NOT_DONE,
            )

            # The distilled result:
            episode = Episode(
                eid=eid,
                url=url,
                title=title,
                pub_date=pub_date,
                description=description,
                duration=duration,
                audio=audio_info,
                transcript=transcript_info,
            )

            episodes.append(episode)

        return episodes

    def _download_rss(self):
        """
        Download the RSS feed from the given URL or file path and save it to a temp file.
        """
        if self._is_url(self.remote_resource):
            try:
                response = requests.get(self.remote_resource, timeout=10)
                response.raise_for_status()
                logger.debug(f"RSS feed downloaded from {self.remote_resource}")

                with open(self.TEMPFILE, "wb") as file:
                    file.write(response.content)
                
                return

            except requests.HTTPError as e:
                logger.error(
                    "Failed to download RSS feed. Check the URL and connection."
                )

                return
        
        try:
            with open(Path(self.remote_resource), "r") as file:
                with open(self.TEMPFILE, "wb") as out_file:
                    out_file.write(file.read().encode("utf-8"))

        except FileNotFoundError:
            logger.error(f"File not found: {self.remote_resource}")

            return

    def _is_url(self, resource: str) -> bool:
        return resource.startswith("http://") or resource.startswith("https://")

    def __repr__(self):
        out = super().__repr__()

        return out
