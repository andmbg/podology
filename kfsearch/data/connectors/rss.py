from datetime import datetime
from pathlib import Path
import requests
from xml.etree import ElementTree
from dataclasses import dataclass, field
from loguru import logger

from kfsearch.data.models import Episode, EpisodeStore, UniqueEpisodeError
from kfsearch.data.connectors.base import Connector


@dataclass
class RSSConnector(Connector):
    """
    Attaches to an EpisodeStore. Given a URL as its 'resource' attribute, downloads the
    RSS feed from the URL and saves it to a file in the store's data directory. Provides
    the populate_store method to extract episode metadata from the RSS feed and save it
    in the EpisodeStore JSON file.
    """
    # The rss_file path is set by the EpisodeStore that the connector attaches to.
    rss_file: Path = None

    def __post_init__(self):
        pass

    def __repr__(self):
        out = super().__repr__()

        return out

    def _download_rss(self):
        response = requests.get(self.resource)
        response.raise_for_status()  # Raise an error for bad status codes

        with open(self.rss_file, "wb") as file:
            file.write(response.content)

    def _extract_episodes(self) -> list[dict]:
        """
        Extract episode metadata from the RSS feed and put it into the EpisodeStore.
        """
        tree = ElementTree.parse(self.rss_file)
        root = tree.getroot()

        ep_metas = []
        for item in root.findall(".//item"):
            ep_meta = {
                "title": item.find("title").text,
                "pub_date": item.find("pubDate").text,
                "guid": item.find("guid").text,
                "description": item.find("description").text,
                "audio_url": item.find("enclosure").attrib["url"],
                "duration": item.find(
                    "{http://www.itunes.com/dtds/podcast-1.0.dtd}duration"
                ).text,
            }
            ep_meta["pub_date"] = datetime.strptime(
                ep_meta["pub_date"], "%a, %d %b %Y %H:%M:%S %z"
            ).strftime("%a, %Y-%m-%d")
            ep_metas.append(ep_meta)

        return ep_metas

    def populate_store(self):
        self._download_rss()
        episodes_data: list = self._extract_episodes()

        # count cases of redundancy to report once instead of 1x per episode:
        redundancies = 0
        additions = 0

        for ep_data in episodes_data:
            try:
                Episode(
                    store=self.store,
                    audio_url=(
                        ep_data.get("enclosure_url")
                        or ep_data.get("audio_url")
                    ),
                    title=ep_data["title"],
                    pub_date=ep_data["pub_date"],
                    description=ep_data["description"],
                    duration=ep_data["duration"],
                )
                additions += 1
            except UniqueEpisodeError:
                # episode already exists in store, so we skip it
                redundancies += 1
                continue

        logger.info(
            f"{redundancies} episodes already present in the Store, {additions} added."
        )
