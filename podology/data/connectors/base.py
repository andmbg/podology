"""
Base class for connectors.
"""

from pathlib import Path
from abc import ABC, abstractmethod
from dataclasses import dataclass

from ...data.Episode import Episode
from ....config import DATA_DIR, PROJECT_NAME


@dataclass
class Connector(ABC):
    """
    Base class for all data connectors.
    The Connector's job is to extract a list of episode metadata from a resource
    (e.g., RSS feed, web page) and make it available to the EpisodeStore.
    The resource is a URL or a file path, depending on the connector.

    attr resource: identifier for the resource to connect to; e.g. URL for RSS feed,
        file path for local file.
    """

    remote_resource: str
    local_rss_file: Path = DATA_DIR / PROJECT_NAME / f"{PROJECT_NAME}.rss"

    def __repr__(self):
        out = f"{self.__class__.__name__}\n  resource={self.remote_resource}\n"

        return out

    @abstractmethod
    def fetch_episodes(self) -> list[Episode]:
        """
        Return a list of Episode objects extracted from the remote resource. Necessarily
        incomplete, as file info and transcription status are not contained there. This
        method is only used to get new episodes or populate a new store.
        """
