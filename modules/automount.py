__author__ = 'Thomas Funk'
__coauthors__ = 'Github Copilot & Gemini'
__date__ = "2026/03/21"

import asyncio
import pyudev
import subprocess
from modules.base import BasePlugin

class AutomountPlugin(BasePlugin):
    async def run(self) -> None:
        self.log.info("Starting device monitoring")
        # Wir lassen das Monitoring in einem separaten Thread laufen,
        # damit asyncio weiterhin auf den Socket reagieren kann.
        await asyncio.to_thread(self._monitor_loop)

    def _monitor_loop(self):
        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        monitor.filter_by(subsystem='block', device_type='partition')

        for device in iter(monitor.poll, None):
            if device.action == 'add':
                self._handle_mount(device)
            elif device.action == 'remove':
                self._handle_unmount(device)

    def _handle_mount(self, device):
        dev_node = device.device_node
        
        # Check gegen die Config
        blacklist = self.config.get("automount", "blacklist") or []
        if dev_node in blacklist:
            self.log.info("Device %s is blacklisted, skipping.", dev_node)
            return

        try:
            # udisksctl nutzt Polkit für Rechteverwaltung
            result = subprocess.run(
                ['udisksctl', 'mount', '-b', dev_node],
                capture_output=True, text=True, check=True
            )
            
            # Mountpoint extrahieren
            mount_point = result.stdout.split("at")[-1].strip()
            self.log.info("Mounted %s at %s", dev_node, mount_point)

            # Nachricht an ALLE (ld-icons, wbar, etc.) senden
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

    def _handle_unmount(self, device):
        self.log.info("Device removed: %s", device.device_node)
        # IPC-Broadcast für 'unmounted' analog zu oben...
        asyncio.run_coroutine_threadsafe(
            self.send_ipc({
                "src": "nsd.automount",
                "type": "broadcast",
                "action": "unmounted",
                "payload": {"device": device.device_node}
            }),
            asyncio.get_event_loop()
        )