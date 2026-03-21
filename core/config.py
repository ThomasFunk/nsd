__author__ = 'Thomas Funk'
__coauthors__ = 'Github Copilot & Gemini'
__date__ = "2026/03/22"

"""Configuration management for nsd.

This module resolves the effective config file path, loads TOML content,
and merges user-defined values into internal defaults.
"""

import copy
import logging
import os
from pathlib import Path
from typing import Any
import tomllib

log = logging.getLogger("nsd.config")

COMPANION_CONFIGS = {
    "h-corners": "h-corners.toml",
    "ld-icons": "ld-icons.toml",
}

class ConfigManager:
    """Load and provide access to daemon configuration values.

    Resolution order for the config file is:
    1) Workspace-local file (`<workspace>/nsd.toml`)
    2) XDG config file (`~/.config/lns/nsd.toml`, or `XDG_CONFIG_HOME`)
    """

    def __init__(self, app_name: str = "lns", config_name: str = "nsd.toml") -> None:
        """Initialize manager, define defaults, and load config immediately."""
        self.app_name = app_name
        self.config_name = config_name

        # Resolve workspace root from this file location.
        self.workspace_root = Path(__file__).resolve().parent.parent

        # Preferred local config inside the repository/workspace.
        self.local_config_path = self.workspace_root / self.config_name

        # Fallback location according to XDG base directory specification.
        xdg_base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        self.config_dir = xdg_base / self.app_name
        self.xdg_config_path = self.config_dir / self.config_name

        # Prefer workspace-local config if present, otherwise use XDG path.
        self.config_path = self.local_config_path if self.local_config_path.exists() else self.xdg_config_path

        # Built-in defaults are always the baseline configuration.
        self.defaults = {
            "global": {
                "socket_path": "/tmp/nsd.sock",
                "log_level": "info",
                "autostart": []
            },
            "modules": {
                "automount": True,
                "notifications": True,
                "labwc_bridge": True,
                "hot_corner_relay": True,
                "clipboard": True,
                "menu_watcher": True,
            },
            "automount": {
                "mount_path": "/media",
                "blacklist": []
            },
            "labwc_bridge": {
                "poll_interval": 1.0,
                "status_command": "labwc-msg -j -t get_outputs",
                "close_window_command": "labwc-msg -t close",
                "switch_workspace_command": "labwc-msg -t workspace {workspace}",
            },
            "hot_corner_relay": {
                "result_broadcast": True,
            },
            "clipboard": {
                "max_items": 20,
                "poll_interval": 0.5,
            },
            "menu_watcher": {
                "enabled": True,
                "extra_paths": [],
                "debounce_seconds": 1.0,
                "include_app_list": False,
            }
        }

        # Keep runtime config as a deep copy to avoid mutating defaults.
        self.config: dict[str, Any] = copy.deepcopy(self.defaults)
        self.load()

    def _load_companion_configs(self, base_dir: Path) -> None:
        """Load optional tool-specific TOML files from *base_dir*.

        These companion files keep `nsd.toml` compact while still allowing
        complex external tools such as `h-corners` or `ld-icons` to have
        dedicated configuration files in the same directory.
        """
        for section_name, file_name in COMPANION_CONFIGS.items():
            companion_path = base_dir / file_name
            if not companion_path.exists():
                continue
            try:
                with companion_path.open("rb") as f:
                    companion_config = tomllib.load(f)
                self.config[section_name] = companion_config
                log.info("Companion configuration loaded from %s.", companion_path)
            except Exception as exc:
                log.error("Failed to load companion config %s: %s", companion_path, exc)

    def _deep_merge(self, source: dict[str, Any], destination: dict[str, Any]) -> dict[str, Any]:
        """Recursively merge `source` into `destination`.

        Values from `source` overwrite existing values in `destination`.
        Nested dictionaries are merged recursively.
        """
        for key, value in source.items():
            if isinstance(value, dict):
                # Ensure a nested dictionary exists before descending.
                node = destination.setdefault(key, {})
                self._deep_merge(value, node)
            else:
                # Scalar/list values overwrite destination directly.
                destination[key] = value
        return destination

    def load(self) -> None:
        """Load TOML config and merge it onto defaults.

        On missing file or parsing errors, defaults remain active.
        """
        # Start from a fresh copy every time load() is called.
        self.config = copy.deepcopy(self.defaults)

        if not self.config_path.exists():
            log.warning(
                "Config not found (%s or %s). Using defaults.",
                self.local_config_path,
                self.xdg_config_path,
            )
            self._load_companion_configs(self.config_path.parent)
            return

        try:
            with self.config_path.open("rb") as f:
                # tomllib expects binary mode for file reading.
                user_config = tomllib.load(f)
                self.config = self._deep_merge(user_config, self.config)
                log.info("Configuration loaded from %s.", self.config_path)
                self._load_companion_configs(self.config_path.parent)
        except Exception as e:
            log.error("Failed to load config: %s. Using defaults.", e)
            self._load_companion_configs(self.config_path.parent)

    def get(self, section: str, key: str | None = None) -> Any:
        """Return a configuration value.

        Args:
            section: Top-level section name (e.g. "global").
            key: Optional key inside the section.

        Returns:
            The full section dict if `key` is None, otherwise the value
            for `section[key]`. Returns None when missing.
        """
        if key:
            return self.config.get(section, {}).get(key)
        return self.config.get(section)

# Example usage
if __name__ == "__main__":
    # Initialize manager
    cfg = ConfigManager()
    
    # Read values
    socket = cfg.get("global", "socket_path")
    is_mount_active = cfg.get("modules", "automount")
    
    print(f"Socket: {socket}")
    print(f"Automount enabled: {is_mount_active}")