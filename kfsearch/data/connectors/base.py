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
        pass
