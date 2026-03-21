__author__ = 'Thomas Funk'
__coauthors__ = 'Github Copilot & Gemini'
__date__ = "2026/03/21"

"""Labwc bridge plugin for control commands and status change broadcasts."""

import asyncio
import json
import shlex
import subprocess
from typing import Any

from modules.base import BasePlugin


class LabwcBridgePlugin(BasePlugin):
    """Expose labwc control actions and publish status changes over nsd IPC."""

    def __init__(self, config: Any, send_ipc_func: Any) -> None:
        super().__init__(config, send_ipc_func)
        bridge_cfg = self.config.get("labwc_bridge") or {}
        self._poll_interval = float(bridge_cfg.get("poll_interval", 1.0))
        self._status_cmd = str(bridge_cfg.get("status_command", "labwc-msg -j -t get_outputs"))
        self._close_cmd = str(bridge_cfg.get("close_window_command", "labwc-msg -t close"))
        self._workspace_cmd = str(
            bridge_cfg.get("switch_workspace_command", "labwc-msg -t workspace {workspace}")
        )
        self._last_status_raw = ""

    def register_handlers(self, daemon: Any) -> None:
        """Register IPC actions that control labwc."""
        daemon.register_command_handler("labwc.close_window", self.handle_close_window)
        daemon.register_command_handler("labwc.switch_workspace", self.handle_switch_workspace)

    def _run_command(self, command: str) -> tuple[int, str, str]:
        args = shlex.split(command)
        result = subprocess.run(args, capture_output=True, text=True)
        return result.returncode, result.stdout.strip(), result.stderr.strip()

    def _status_payload(self, raw: str) -> dict[str, Any]:
        payload: dict[str, Any] = {"raw": raw}
        try:
            payload["data"] = json.loads(raw)
        except json.JSONDecodeError:
            payload["data"] = None
        return payload

    async def _execute_and_broadcast_result(
        self,
        action: str,
        command: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        rc, stdout, stderr = await asyncio.to_thread(self._run_command, command)
        payload: dict[str, Any] = {
            "action": action,
            "ok": rc == 0,
            "returncode": rc,
            "stdout": stdout,
            "stderr": stderr,
        }
        if context:
            payload.update(context)
        await self.send_ipc(
            {
                "src": "nsd.labwc_bridge",
                "type": "broadcast",
                "action": "labwc_command_result",
                "payload": payload,
            }
        )

    async def handle_close_window(self, payload: dict[str, Any]) -> None:
        await self._execute_and_broadcast_result("labwc.close_window", self._close_cmd, payload or None)

    async def handle_switch_workspace(self, payload: dict[str, Any]) -> None:
        workspace = payload.get("workspace") if isinstance(payload, dict) else None
        if workspace in (None, ""):
            await self.send_ipc(
                {
                    "src": "nsd.labwc_bridge",
                    "type": "broadcast",
                    "action": "labwc_command_result",
                    "payload": {
                        "action": "labwc.switch_workspace",
                        "ok": False,
                        "returncode": -1,
                        "stdout": "",
                        "stderr": "missing workspace",
                    },
                }
            )
            return

        cmd = self._workspace_cmd.format(workspace=workspace)
        await self._execute_and_broadcast_result(
            "labwc.switch_workspace",
            cmd,
            {"workspace": workspace},
        )

    async def _poll_status_once(self) -> None:
        rc, stdout, stderr = await asyncio.to_thread(self._run_command, self._status_cmd)
        if rc != 0:
            self.log.debug("Status command failed: %s", stderr)
            return
        if stdout == self._last_status_raw:
            return
        self._last_status_raw = stdout
        await self.send_ipc(
            {
                "src": "nsd.labwc_bridge",
                "type": "broadcast",
                "action": "labwc.status_changed",
                "payload": self._status_payload(stdout),
            }
        )

    async def run(self) -> None:
        """Run periodic status polling loop."""
        self.log.info("Labwc bridge started")
        while True:
            await self._poll_status_once()
            await asyncio.sleep(self._poll_interval)
