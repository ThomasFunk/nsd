__author__ = 'Thomas Funk'
__coauthors__ = 'Github Copilot & Gemini'
__date__ = "2026/03/20"

import abc

class BasePlugin(abc.ABC):
    def __init__(self, config, send_ipc_func):
        self.config = config
        self.send_ipc = send_ipc_func
        self.name = self.__class__.__name__

    @abc.abstractmethod
    async def run(self):
        """Hier kommt die Hauptlogik des Plugins rein (Endlosschleife etc.)"""
        pass