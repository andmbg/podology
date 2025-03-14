from pathlib import Path
import requests
from xml.etree import ElementTree
from dataclasses import dataclass
from loguru import logger

from kfsearch.data.models import Episode, EpisodeStore


@dataclass
class PodcastRSSExtractor:
    rss_link: str
    store: EpisodeStore
    rss_file: Path = None

    def __post_init__(self):
        self.rss_file = self.store.path / "rss.xml"

    def download_rss(self, force: bool = False):

        # Check first if RSS file already exists, only update if force is True:
        if self.rss_file.exists() and not force:
            logger.info("RSS file already exists, use force=True to download anyway.")
            return

        response = requests.get(self.rss_link)
        response.raise_for_status()  # Raise an error for bad status codes

        with open(self.rss_file, "wb") as file:
            file.write(response.content)

        self.populate_store()

    def extract_episodes(self) -> list[dict]:
        if not self.rss_file:
            raise ValueError("RSS file not downloaded. Call download_rss() first.")

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
            ep_metas.append(ep_meta)

        return ep_metas

    def populate_store(self):
        episodes_data = self.extract_episodes()
        for ep_data in episodes_data:
            episode = Episode(
                store=self.store,
                audio_url=ep_data["enclosure_url"],
                title=ep_data["title"],
                pub_date=ep_data["pub_date"],
                description=ep_data["description"],
                duration=ep_data["duration"],
            )
            self.store.add(episode)
