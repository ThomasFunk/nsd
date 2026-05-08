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
    """Labwc control and status bridge.

    Exposes IPC command handlers for common labwc actions and broadcasts status
    changes detected via periodic polling.
    """

    def __init__(self, config: Any, send_ipc_func: Any) -> None:
        """Initialize labwc bridge settings.

        Parameters
        ----------
        config : Any
            Configuration provider.
        send_ipc_func : Any
            Async IPC send callback.
        """
        super().__init__(config, send_ipc_func)
        bridge_cfg = self.config.get("labwc_bridge") or {}
        self._poll_interval = float(bridge_cfg.get("poll_interval", 1.0))
        self._status_cmd = str(bridge_cfg.get("status_command", "labwc-msg -j -t get_outputs"))
        self._close_cmd = str(bridge_cfg.get("close_window_command", "labwc-msg -t close"))
        self._workspace_cmd = str(
            bridge_cfg.get("switch_workspace_command", "labwc-msg -t workspace {workspace}")
        )
        self._reconfigure_cmd = str(bridge_cfg.get("reconfigure_command", "labwc --reconfigure"))
        self._last_status_raw = ""

    def register_handlers(self, daemon: Any) -> None:
        """Register IPC command and event handlers.

        Parameters
        ----------
        daemon : Any
            Daemon instance exposing registration methods.

        Returns
        -------
        None
        """
        daemon.register_command_handler("labwc.close_window", self.handle_close_window)
        daemon.register_command_handler("labwc.switch_workspace", self.handle_switch_workspace)
        daemon.register_command_handler("labwc.reconfigure", self.handle_reconfigure)
        # React to menu watcher updates so labwc can rebuild app menu entries.
        daemon.register_event_handler("nsd.menu_watcher:apps_changed", self.handle_apps_changed)
        daemon.register_event_handler("nsd.nde_config_assembler:reconfigure_requested", self.handle_reconfigure_requested)

    def _run_command(self, command: str) -> tuple[int, str, str]:
        """Execute command string and return process result.

        Parameters
        ----------
        command : str
            Command to execute.

        Returns
        -------
        tuple[int, str, str]
            ``(returncode, stdout, stderr)``.
        """
        args = shlex.split(command)
        result = subprocess.run(args, capture_output=True, text=True)
        return result.returncode, result.stdout.strip(), result.stderr.strip()

    def _status_payload(self, raw: str) -> dict[str, Any]:
        """Build structured status payload from raw status output.

        Parameters
        ----------
        raw : str
            Raw status command output.

        Returns
        -------
        dict[str, Any]
            Payload with raw text and optional parsed JSON.
        """
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
        """Execute command and broadcast standardized result payload.

        Parameters
        ----------
        action : str
            Logical action name reported to clients.
        command : str
            Shell command to execute.
        context : dict[str, Any] | None, default=None
            Optional extra fields merged into result payload.

        Returns
        -------
        None
        """
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
        """Handle close-window command.

        Parameters
        ----------
        payload : dict[str, Any]
            Optional command context.

        Returns
        -------
        None
        """
        await self._execute_and_broadcast_result("labwc.close_window", self._close_cmd, payload or None)

    async def handle_switch_workspace(self, payload: dict[str, Any]) -> None:
        """Handle workspace switch command.

        Parameters
        ----------
        payload : dict[str, Any]
            Command payload expected to include ``workspace``.

        Returns
        -------
        None
        """
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

    async def handle_reconfigure(self, payload: dict[str, Any]) -> None:
        """Handle explicit labwc reconfigure command.

        Parameters
        ----------
        payload : dict[str, Any]
            Optional command context.

        Returns
        -------
        None
        """
        await self._execute_and_broadcast_result("labwc.reconfigure", self._reconfigure_cmd, payload or None)

    async def _poll_status_once(self) -> None:
        """Poll labwc status once and broadcast on change.

        Returns
        -------
        None
        """
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
        """Run periodic status polling loop.

        Returns
        -------
        None
        """
        self.log.info("Labwc bridge started")
        while True:
            await self._poll_status_once()
            await asyncio.sleep(self._poll_interval)

    async def handle_apps_changed(self, payload: dict[str, Any]) -> None:
        """Handle menu change event by triggering labwc reconfigure.

        Parameters
        ----------
        payload : dict[str, Any]
            Event payload from ``nsd.menu_watcher:apps_changed``.

        Returns
        -------
        None
        """
        self.log.info("Menu watcher reported changes, running labwc reconfigure")
        await self.handle_reconfigure(payload)

    async def handle_reconfigure_requested(self, payload: dict[str, Any]) -> None:
        """Handle internal reconfigure request events from other plugins.

        Parameters
        ----------
        payload : dict[str, Any]
            Event payload from ``nsd.nde_config_assembler:reconfigure_requested``.

        Returns
        -------
        None
        """
        self.log.info("Received internal reconfigure request from %s", payload.get("source", "unknown"))
        await self.handle_reconfigure(payload)
