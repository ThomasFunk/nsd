__author__ = 'Thomas Funk'
__coauthors__ = 'Github Copilot & Gemini'
__date__ = "2026/03/21"

"""Automount plugin for block-device events and IPC broadcasts."""

import asyncio
import pyudev
import subprocess
from typing import Any
from modules.base import BasePlugin

# Filesystem types that are safe to auto-mount.
MOUNTABLE_FS_TYPES = {
    "vfat", "exfat", "ntfs", "ext2", "ext3", "ext4",
    "btrfs", "xfs", "f2fs", "iso9660", "udf",
}


class AutomountPlugin(BasePlugin):
    """Automount plugin for block-device events.

    Monitors udev partition add/remove events, mounts supported filesystems
    via ``udisksctl``, and emits IPC broadcasts for mount state changes.
    """

    def __init__(self, config: Any, send_ipc_func: Any) -> None:
        """Initialize plugin state.

        Parameters
        ----------
        config : Any
            Configuration provider passed by the daemon.
        send_ipc_func : Any
            Async callback used to send IPC messages.
        """
        super().__init__(config, send_ipc_func)
        # Maps dev_node -> {"mount_point": str, "label": str, "fs_type": str}
        self._mounted: dict[str, dict[str, str]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    async def run(self) -> None:
        """Start monitoring for block-device events.

        Captures the current asyncio event loop and runs the blocking udev
        polling loop in a worker thread.

        Returns
        -------
        None
        """
        # Store the loop reference before entering the thread so _ipc() can use it safely.
        self._loop = asyncio.get_running_loop()
        self.log.info("Starting device monitoring")
        # Run pyudev polling in a separate thread because it is blocking.
        await asyncio.to_thread(self._monitor_loop)

    # helpers ------------------------------------------------------------------

    def _ipc(self, msg: dict[str, Any]) -> None:
        """Schedule an IPC send from a non-async thread.

        Parameters
        ----------
        msg : dict[str, Any]
            IPC message payload to send.

        Returns
        -------
        None
        """
        if self._loop:
            asyncio.run_coroutine_threadsafe(self.send_ipc(msg), self._loop)

    def _device_info(self, device: pyudev.Device) -> dict[str, str]:
        """Extract common filesystem metadata from a udev device.

        Parameters
        ----------
        device : pyudev.Device
            Udev device object.

        Returns
        -------
        dict[str, str]
            Dictionary with ``label``, ``uuid``, and ``fs_type`` keys.
        """
        return {
            "label":   device.get("ID_FS_LABEL") or "",
            "uuid":    device.get("ID_FS_UUID") or "",
            "fs_type": device.get("ID_FS_TYPE") or "",
        }

    # monitor ------------------------------------------------------------------

    def _monitor_loop(self) -> None:
        """Run the blocking udev monitor loop.

        Listens for partition add/remove events and dispatches them to
        mount/unmount handlers.

        Returns
        -------
        None
        """
        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        monitor.filter_by(subsystem="block", device_type="partition")
        # start() must be called before the first poll().
        monitor.start()

        # Poll indefinitely and dispatch events.
        for device in iter(monitor.poll, None):
            if device.action == "add":
                self._handle_mount(device)
            elif device.action == "remove":
                self._handle_unmount(device)

    # handlers -----------------------------------------------------------------

    def _handle_mount(self, device: pyudev.Device) -> None:
        """Handle udev add event by mounting and broadcasting state.

        Parameters
        ----------
        device : pyudev.Device
            Newly detected block partition device.

        Returns
        -------
        None

        Raises
        ------
        subprocess.CalledProcessError
            Internally caught and logged if ``udisksctl mount`` fails.
        """
        dev_node = device.device_node
        info = self._device_info(device)

        # Respect blacklist entries from config.
        blacklist = self.config.get("automount", "blacklist") or []
        if dev_node in blacklist:
            self.log.info("Device %s is blacklisted, skipping.", dev_node)
            return

        # Skip devices with no known filesystem or with non-mountable types (e.g. swap).
        fs_type = info["fs_type"]
        if fs_type not in MOUNTABLE_FS_TYPES:
            self.log.info(
                "Device %s has fs_type '%s', skipping auto-mount.", dev_node, fs_type
            )
            return

        try:
            # udisksctl triggers privileged actions via Polkit — no sudo needed.
            result = subprocess.run(
                ["udisksctl", "mount", "-b", dev_node],
                capture_output=True, text=True, check=True,
            )

            # udisksctl output: "Mounted /dev/sdX at /run/media/user/LABEL."
            # Strip trailing period and whitespace that udisksctl appends.
            raw = result.stdout.split(" at ")[-1]
            mount_point = raw.strip().rstrip(".")
            self.log.info("Mounted %s at %s (fs: %s)", dev_node, mount_point, fs_type)

            # Remember mount point for use in _handle_unmount.
            self._mounted[dev_node] = {**info, "mount_point": mount_point}

            self._ipc({
                "src": "nsd.automount",
                "type": "broadcast",
                "action": "mounted",
                "payload": {
                    "device":      dev_node,
                    "mount_point": mount_point,
                    "label":       info["label"],
                    "uuid":        info["uuid"],
                    "fs_type":     fs_type,
                },
            })

        except subprocess.CalledProcessError as e:
            self.log.error("Failed to mount %s: %s", dev_node, e.stderr.strip())

    def _handle_unmount(self, device: pyudev.Device) -> None:
        """Handle udev remove event and broadcast unmount state.

        Parameters
        ----------
        device : pyudev.Device
            Removed block partition device.

        Returns
        -------
        None
        """
        dev_node = device.device_node
        info = self._mounted.pop(dev_node, {})
        mount_point = info.get("mount_point", "")

        self.log.info("Device removed: %s (was at %s)", dev_node,
                      mount_point or "unknown")

        self._ipc({
            "src": "nsd.automount",
            "type": "broadcast",
            "action": "unmounted",
            "payload": {
                "device":      dev_node,
                "mount_point": mount_point,
                "label":       info.get("label", ""),
                "uuid":        info.get("uuid", ""),
            },
        })