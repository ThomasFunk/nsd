__author__ = 'Thomas Funk'
__coauthors__ = 'Github Copilot & Gemini'
__date__ = "2026/03/21"

import copy
import logging
import os
from pathlib import Path
from typing import Any
import tomllib

class ConfigManager:
    def __init__(self, app_name: str = "lns", config_name: str = "nsd.toml") -> None:
        self.app_name = app_name
        self.config_name = config_name
        self.workspace_root = Path(__file__).resolve().parent.parent
        self.local_config_path = self.workspace_root / self.config_name
        xdg_base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        self.config_dir = xdg_base / self.app_name
        self.xdg_config_path = self.config_dir / self.config_name
        self.config_path = self.local_config_path if self.local_config_path.exists() else self.xdg_config_path

        self.defaults = {
            "global": {
                "socket_path": "/tmp/nsd.sock",
                "log_level": "info",
                "autostart": []
            },
            "modules": {
                "automount": True,
                "notifications": True,
                "labwc_bridge": True
            },
            "automount": {
                "mount_path": "/media",
                "blacklist": []
            }
        }
        self.config: dict[str, Any] = copy.deepcopy(self.defaults)
        self.load()

    def _deep_merge(self, source: dict[str, Any], destination: dict[str, Any]) -> dict[str, Any]:
        """Überlagert Defaults mit Werten aus der Datei (rekursiv)."""
        for key, value in source.items():
            if isinstance(value, dict):
                node = destination.setdefault(key, {})
                self._deep_merge(value, node)
            else:
                destination[key] = value
        return destination

    def load(self) -> None:
        """Lädt die TOML-Datei und merget sie mit den Defaults."""
        self.config = copy.deepcopy(self.defaults)

        if not self.config_path.exists():
            logging.warning(
                "Config nicht gefunden (%s oder %s). Nutze Defaults.",
                self.local_config_path,
                self.xdg_config_path,
            )
            return

        try:
            with self.config_path.open("rb") as f:
                user_config = tomllib.load(f)
                self.config = self._deep_merge(user_config, self.config)
                logging.info(f"Konfiguration aus {self.config_path} geladen.")
        except Exception as e:
            logging.error(f"Fehler beim Laden der Config: {e}. Nutze Defaults.")

    def get(self, section: str, key: str | None = None) -> Any:
        """Bequemer Zugriff auf Werte."""
        if key:
            return self.config.get(section, {}).get(key)
        return self.config.get(section)

# --- Beispielnutzung ---
if __name__ == "__main__":
    # Initialisierung
    cfg = ConfigManager()
    
    # Zugriff auf Werte
    socket = cfg.get("global", "socket_path")
    is_mount_active = cfg.get("modules", "automount")
    
    print(f"Socket: {socket}")
    print(f"Automount aktiv: {is_mount_active}")