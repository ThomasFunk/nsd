__author__ = 'Thomas Funk'
__coauthors__ = 'Github Copilot & Gemini'
__date__ = "2026/03/21"

"""Base plugin abstraction for nsd modules."""

import abc
import logging
from typing import Any, Callable, Coroutine

class BasePlugin(abc.ABC):
    """Shared base class for all daemon plugins."""

    def __init__(self, config: Any, send_ipc_func: Callable[..., Coroutine]) -> None:
        """Store shared dependencies and initialize plugin logger."""
        self.config = config
        self.send_ipc = send_ipc_func
        self.name = self.__class__.__name__
        self.log = logging.getLogger(f"nsd.{self.name.lower()}")

    @abc.abstractmethod
    async def run(self) -> None:
        """Main plugin loop. Must be overridden by subclasses."""
        pass