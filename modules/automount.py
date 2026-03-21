__author__ = 'Thomas Funk'
__coauthors__ = 'Github Copilot & Gemini'
__date__ = "2026/03/21"

"""Automount plugin for block-device events and IPC broadcasts."""

import asyncio
import pyudev
import subprocess
from modules.base import BasePlugin

class AutomountPlugin(BasePlugin):
    """Monitor udev events and mount/unmount partitions automatically."""

    async def run(self) -> None:
        """Start device monitoring in a worker thread to keep asyncio responsive."""
        self.log.info("Starting device monitoring")
        # Run pyudev polling in a separate thread because it is blocking.
        await asyncio.to_thread(self._monitor_loop)

    def _monitor_loop(self) -> None:
        """Blocking udev event loop for partition add/remove events."""
        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        monitor.filter_by(subsystem='block', device_type='partition')

        # Poll indefinitely and dispatch events.
        for device in iter(monitor.poll, None):
            if device.action == 'add':
                self._handle_mount(device)
            elif device.action == 'remove':
                self._handle_unmount(device)

    def _handle_mount(self, device) -> None:
        """Mount a newly added partition and broadcast a mounted event."""
        dev_node = device.device_node
        
        # Respect blacklist entries from config.
        blacklist = self.config.get("automount", "blacklist") or []
        if dev_node in blacklist:
            self.log.info("Device %s is blacklisted, skipping.", dev_node)
            return

        try:
            # udisksctl triggers privileged actions via Polkit.
            result = subprocess.run(
                ['udisksctl', 'mount', '-b', dev_node],
                capture_output=True, text=True, check=True
            )
            
            # Parse mount point from udisksctl output.
            mount_point = result.stdout.split("at")[-1].strip()
            self.log.info("Mounted %s at %s", dev_node, mount_point)

            # Broadcast mount event for subscribers (e.g. UI tools).
            asyncio.run_coroutine_threadsafe(
                self.send_ipc({
                    "src": "nsd.automount",
                    "type": "broadcast",
                    "action": "mounted",
                    "payload": {"device": dev_node, "mount_point": mount_point}
                }),
                asyncio.get_event_loop()
            )

        except subprocess.CalledProcessError as e:
            self.log.error("Failed to mount %s: %s", dev_node, e.stderr)

    def _handle_unmount(self, device) -> None:
        """Broadcast an unmounted event when a partition disappears."""
        self.log.info("Device removed: %s", device.device_node)
        # Broadcast unmount event to keep external tools in sync.
        asyncio.run_coroutine_threadsafe(
            self.send_ipc({
                "src": "nsd.automount",
                "type": "broadcast",
                "action": "unmounted",
                "payload": {"device": device.device_node}
            }),
            asyncio.get_event_loop()
        )