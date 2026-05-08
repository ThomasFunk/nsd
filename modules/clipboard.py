__author__ = 'Thomas Funk'
__coauthors__ = 'Github Copilot & Gemini'
__date__ = "2026/03/21"

"""Clipboard history plugin for NSD.

Tracks clipboard text changes on Wayland and provides history access via IPC
command handlers.
"""

import asyncio
import subprocess
from typing import Any

from modules.base import BasePlugin


class ClipboardPlugin(BasePlugin):
    """Clipboard history plugin.

    Maintains an in-memory clipboard history and exposes query/clear handlers
    over NSD IPC.
    """

    def __init__(self, config: Any, send_ipc_func: Any) -> None:
        """Initialize clipboard plugin state.

        Parameters
        ----------
        config : Any
            Configuration provider.
        send_ipc_func : Any
            Async IPC send callback.
        """
        super().__init__(config, send_ipc_func)
        # Clipboard-specific config lives under [clipboard] in nsd.toml.
        clipboard_cfg = self.config.get("clipboard") or {}
        # Limit history size to avoid unbounded memory growth.
        self.max_items = self._safe_int(clipboard_cfg.get("max_items", 20), fallback=20, minimum=1)
        # Polling is simple/reliable on Wayland and keeps this plugin decoupled.
        self.poll_interval = self._safe_float(clipboard_cfg.get("poll_interval", 0.5), fallback=0.5, minimum=0.1)
        # Newest entry is always at index 0.
        self.history: list[str] = []

    @staticmethod
    def _safe_int(value: Any, fallback: int, minimum: int = 0) -> int:
        """Parse an integer config value safely.

        Parameters
        ----------
        value : Any
            Input value to parse.
        fallback : int
            Value returned when parsing fails.
        minimum : int, default=0
            Lower bound for parsed result.

        Returns
        -------
        int
            Parsed and clamped integer.
        """
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return fallback
        return max(minimum, parsed)

    @staticmethod
    def _safe_float(value: Any, fallback: float, minimum: float = 0.0) -> float:
        """Parse a float config value safely.

        Parameters
        ----------
        value : Any
            Input value to parse.
        fallback : float
            Value returned when parsing fails.
        minimum : float, default=0.0
            Lower bound for parsed result.

        Returns
        -------
        float
            Parsed and clamped float.
        """
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return fallback
        return max(minimum, parsed)

    def register_handlers(self, daemon: Any) -> None:
        """Register clipboard-related IPC command handlers.

        Parameters
        ----------
        daemon : Any
            Daemon instance exposing ``register_command_handler``.

        Returns
        -------
        None
        """
        # Keep short and namespaced aliases to ease migration of existing clients.
        daemon.register_command_handler("get_history", self.handle_get_history)
        daemon.register_command_handler("clipboard.get_history", self.handle_get_history)
        daemon.register_command_handler("clear", self.handle_clear_history)
        daemon.register_command_handler("clipboard.clear", self.handle_clear_history)

    async def run(self) -> None:
        """Run clipboard polling loop.

        Returns
        -------
        None
        """
        self.log.info("Clipboard watcher started (poll_interval=%.2fs, max_items=%d)", self.poll_interval, self.max_items)
        while True:
            await self._check_clipboard()
            await asyncio.sleep(self.poll_interval)

    def _read_clipboard_text(self) -> str:
        """Read current clipboard text using ``wl-paste``.

        Returns
        -------
        str
            Clipboard text, or an empty string if unavailable/non-text.

        """
        try:
            result = subprocess.run(
                ["wl-paste", "-n"],
                capture_output=True,
                text=True,
                check=False,
            )
            # Non-zero often means no textual clipboard content right now.
            if result.returncode != 0:
                return ""
            return result.stdout.strip()
        except Exception:
            # Clipboard backends can fail transiently; ignore and retry next cycle.
            return ""

    async def _check_clipboard(self) -> None:
        """Check clipboard for changes and broadcast updates.

        Returns
        -------
        None
        """
        # Run blocking wl-paste call in a thread to keep asyncio loop responsive.
        current_text = await asyncio.to_thread(self._read_clipboard_text)
        if not current_text:
            return

        # Skip duplicate consecutive copies.
        if self.history and current_text == self.history[0]:
            return

        self.history.insert(0, current_text)
        if len(self.history) > self.max_items:
            # Keep only the newest N entries.
            self.history = self.history[:self.max_items]

        self.log.info("Clipboard entry added (%d items)", len(self.history))
        await self.send_ipc(
            {
                "src": "nsd.clipboard",
                "type": "broadcast",
                "action": "clipboard.history_updated",
                "payload": {"count": len(self.history)},
            }
        )

    async def handle_get_history(self, _payload: dict[str, Any]) -> dict[str, Any]:
        """Return current clipboard history.

        Parameters
        ----------
        _payload : dict[str, Any]
            Unused request payload.

        Returns
        -------
        dict[str, Any]
            History items and count.
        """
        return {
            "items": list(self.history),
            "count": len(self.history),
        }

    async def handle_clear_history(self, _payload: dict[str, Any]) -> dict[str, Any]:
        """Clear in-memory history.

        Parameters
        ----------
        _payload : dict[str, Any]
            Unused request payload.

        Returns
        -------
        dict[str, Any]
            Resulting history state.
        """
        # Explicit clear action enables one-click "wipe history" in UI tools.
        self.history = []
        return {"count": 0, "status": "cleared"}