# kfsearch/data/connectors/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Connector(ABC):
    """
    Base class for all data connectors. Connectors are responsible for getting episode metadata.
    """
    resource: str
    store: "EpisodeStore" = field(default=None, init=False)

    def __repr__(self):
        out = f"{self.__class__.__name__}\n  resource={self.resource}\n"
        if self.store:
            out += f"  store={self.store.name}\n"
        else:
            out += f"  store=None\n"

        return out

    @abstractmethod
    def populate_store(self):
        """
        The main utility of the Connector class and method that each subclass must
        implement. This method is responsible for populating the EpisodeStore with the
        metadata extracted from the resource. For each entity in the source metadata, it
        instantiates an Episode object in the attached EpisodeStore with attributes
          - audio_url,
          - title,
          - pub_date,
          - description,
          - duration.
        """
        pass
