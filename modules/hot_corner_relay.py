__author__ = 'Thomas Funk'
__coauthors__ = 'Github Copilot & Gemini'
__date__ = "2026/03/21"

"""Relay hot-corner trigger commands received from external clients."""

import asyncio
import subprocess
from typing import Any

from modules.base import BasePlugin


class HotCornerRelayPlugin(BasePlugin):
    """Execute relayed hot-corner commands received via nsd IPC."""

    def __init__(self, config: Any, send_ipc_func: Any) -> None:
        super().__init__(config, send_ipc_func)
        relay_cfg = self.config.get("hot_corner_relay") or {}
        self._broadcast_results = bool(relay_cfg.get("result_broadcast", True))

    def register_handlers(self, daemon: Any) -> None:
        """Register the hot-corner trigger command handler on the daemon."""
        daemon.register_command_handler("hotcorner.trigger", self.handle_trigger)

    def _run_command(self, command: str) -> tuple[int, str, str]:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return result.returncode, result.stdout.strip(), result.stderr.strip()

    async def handle_trigger(self, payload: dict[str, Any]) -> None:
        """Execute the relayed shell command and optionally broadcast the result."""
        command = str((payload or {}).get("command") or "").strip()
        result_payload: dict[str, Any] = {
            "corner": (payload or {}).get("corner", ""),
            "name": (payload or {}).get("name", ""),
            "command": command,
        }

        if not command:
            result_payload.update(
                {
                    "ok": False,
                    "returncode": -1,
                    "stdout": "",
                    "stderr": "missing command",
                }
            )
        else:
            rc, stdout, stderr = await asyncio.to_thread(self._run_command, command)
            result_payload.update(
                {
                    "ok": rc == 0,
                    "returncode": rc,
                    "stdout": stdout,
                    "stderr": stderr,
                }
            )

        if self._broadcast_results:
            await self.send_ipc(
                {
                    "src": "nsd.hot_corner_relay",
                    "type": "broadcast",
                    "action": "hotcorner.command_result",
                    "payload": result_payload,
                }
            )

    async def run(self) -> None:
        """Keep the plugin task alive after handler registration."""
        self.log.info("Hot-corner relay active")
        while True:
            await asyncio.sleep(3600)
