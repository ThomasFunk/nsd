__author__ = 'Thomas Funk'
__coauthors__ = 'Github Copilot & Gemini'
__date__ = "2026/03/21"

"""Dynamic plugin discovery and initialization for nsd."""

import importlib
import inspect
import pathlib
import logging
from typing import Any, Callable, Coroutine
from modules.base import BasePlugin

log = logging.getLogger("nsd.loader")

class PluginLoader:
    """Load plugin classes from the modules package and instantiate them."""

    def __init__(self, config: Any, send_ipc_func: Callable[..., Coroutine]) -> None:
        """Store shared dependencies that will be passed to each plugin."""
        self.config = config
        self.send_ipc = send_ipc_func
        self.plugins: list[BasePlugin] = []

    def load_plugins(self) -> list[BasePlugin]:
        """Discover plugin modules and return instantiated plugin objects."""
        # Resolve the absolute path of the modules directory.
        plugins_path = pathlib.Path(__file__).parent.parent / "modules"
        
        # Iterate over all Python files in modules/ except support files.
        for file in plugins_path.glob("*.py"):
            if file.name in ["__init__.py", "base.py"]:
                continue

            # Convert file name into import path, e.g. modules.automount.
            module_name = f"modules.{file.stem}"
            try:
                module = importlib.import_module(module_name)

                # Find classes that inherit from BasePlugin.
                for name, obj in inspect.getmembers(module):
                    if inspect.isclass(obj) and issubclass(obj, BasePlugin) and obj is not BasePlugin:
                        log.info("Plugin loaded: %s", name)
                        self.plugins.append(obj(self.config, self.send_ipc))
            except Exception as e:
                log.error("Failed to load %s: %s", module_name, e)

        return self.plugins