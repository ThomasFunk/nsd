__author__ = 'Thomas Funk'
__coauthors__ = 'Github Copilot & Gemini'
__date__ = "2026/03/21"

"""Base plugin abstraction for nsd modules."""

import abc
import logging
from typing import Any, Callable, Coroutine

class BasePlugin(abc.ABC):
    """Base class for all NSD daemon plugins.

    Provides shared dependencies such as configuration access, IPC send
    callback, and per-plugin logger initialization.
    """

    def __init__(self, config: Any, send_ipc_func: Callable[..., Coroutine]) -> None:
        """Initialize shared plugin dependencies.

        Parameters
        ----------
        config : Any
            Configuration provider used by plugin implementations.
        send_ipc_func : Callable[..., Coroutine]
            Async callable used to publish IPC messages.
        """
        self.config = config
        self.send_ipc = send_ipc_func
        self.name = self.__class__.__name__
        self.log = logging.getLogger(f"nsd.{self.name.lower()}")

    @abc.abstractmethod
    async def run(self) -> None:
        """Run the plugin main loop.

        Returns
        -------
        None

        Notes
        -----
        Must be implemented by subclasses.
        """
        pass