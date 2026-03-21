__author__ = 'Thomas Funk'
__coauthors__ = 'Github Copilot & Gemini'
__date__ = "2026/03/20"

import importlib
import inspect
import pathlib
import logging
from modules.base import BasePlugin

class PluginLoader:
    def __init__(self, config, send_ipc_func):
        self.config = config
        self.send_ipc = send_ipc_func
        self.plugins = []

    def load_plugins(self):
        plugins_path = pathlib.Path(__file__).parent.parent / "modules"
        
        for file in plugins_path.glob("*.py"):
            if file.name in ["__init__.py", "base.py"]:
                continue

            module_name = f"modules.{file.stem}"
            try:
                module = importlib.import_module(module_name)
                for name, obj in inspect.getmembers(module):
                    if inspect.isclass(obj) and issubclass(obj, BasePlugin) and obj is not BasePlugin:
                        logging.info(f"[Loader] Plugin gefunden: {name}")
                        self.plugins.append(obj(self.config, self.send_ipc))
            except Exception as e:
                logging.error(f"[Loader] Fehler beim Laden von {module_name}: {e}")

        return self.plugins