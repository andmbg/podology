from abc import ABC, abstractmethod
import json
import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv, find_dotenv

from loguru import logger
import requests
from dash.html import Div

load_dotenv(find_dotenv(), override=True)




class ScrollAnimator(ABC):
    """
    Base class for generating html elements coupled with the scroll position of a
    transcript in our dashboard.
    """

    def __init__(self, eid: str, width: int = 120):
        self.eid = eid
        self.width = width

    @abstractmethod
    def to_dash(self) -> Div:
        """Convert the animator to a Dash HTML component."""
        pass
