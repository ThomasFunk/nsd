__author__ = 'Thomas Funk'
__coauthors__ = 'Github Copilot & Gemini'
__date__ = "2026/03/21"

"""Menu watcher plugin for .desktop application directories."""

import asyncio
import pathlib
from typing import Any

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except Exception:
    Observer = None
    FileSystemEventHandler = object

from modules.base import BasePlugin


class MenuEventHandler(FileSystemEventHandler):
    """Watchdog event adapter that filters for `.desktop` file changes."""

    def __init__(self, callback):
        """Store callback invoked when relevant file changes are detected."""
        super().__init__()
        self.callback = callback

    def on_any_event(self, event):
        """Handle any filesystem event and trigger callback for desktop files only."""
        # Ignore directory-level and non-desktop events to reduce noise.
        if event.is_directory or not event.src_path.endswith('.desktop'):
            return
        self.callback()


class MenuWatcherPlugin(BasePlugin):
    """Monitor application menu directories and notify clients about changes."""

    def __init__(self, config: Any, send_ipc_func: Any) -> None:
        """Read watcher config, initialize paths, and prepare debounce state."""
        super().__init__(config, send_ipc_func)
        watcher_cfg = self.config.get("menu_watcher") or {}

        # Default XDG application directories (system + user scope).
        self.paths = [
            pathlib.Path("/usr/share/applications"),
            pathlib.Path.home() / ".local/share/applications",
        ]
        # Optional custom directories from config.
        for extra in watcher_cfg.get("extra_paths", []) or []:
            text = str(extra).strip()
            if text:
                self.paths.append(pathlib.Path(text))

        # Debounce avoids event storms during package installations.
        self.debounce_seconds = self._safe_float(watcher_cfg.get("debounce_seconds", 1.0), fallback=1.0, minimum=0.1)
        # Optional full app list in each apps_changed broadcast.
        self.include_app_list = bool(watcher_cfg.get("include_app_list", False))

        self._observer = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._debounce_task: asyncio.Task | None = None

    @staticmethod
    def _safe_float(value: Any, fallback: float, minimum: float = 0.0) -> float:
        """Parse float config values safely with fallback and minimum clamping."""
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return fallback
        return max(minimum, parsed)

    def register_handlers(self, daemon: Any) -> None:
        """Register IPC command handlers for menu app listing queries."""
        # Keep short + namespaced aliases for client compatibility.
        daemon.register_command_handler("get_apps", self.handle_get_apps)
        daemon.register_command_handler("menu.get_apps", self.handle_get_apps)

    def _trigger_reload(self) -> None:
        """Thread-safe trigger entrypoint called from watchdog callback thread."""
        if self._loop is None:
            return
        # Forward to asyncio loop because watchdog callbacks are not in loop thread.
        self._loop.call_soon_threadsafe(self._schedule_debounce)

    def _schedule_debounce(self) -> None:
        """Reset and schedule debounce task for coalesced update emission."""
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()
        self._debounce_task = self._loop.create_task(self._debounced_emit())

    async def _debounced_emit(self) -> None:
        """Wait debounce window and then send one consolidated update signal."""
        try:
            await asyncio.sleep(self.debounce_seconds)
        except asyncio.CancelledError:
            return
        await self._send_update_signal()

    def _collect_app_ids(self) -> list[str]:
        """Collect sorted `.desktop` filenames from all configured watch paths."""
        items = set()
        for path in self.paths:
            if not path.exists() or not path.is_dir():
                continue
            for desktop_file in path.glob("*.desktop"):
                items.add(desktop_file.name)
        return sorted(items)

    async def _send_update_signal(self) -> None:
        """Broadcast app-change notification to IPC clients."""
        payload: dict[str, Any] = {"info": "XDG desktop files updated"}
        if self.include_app_list:
            # App scanning is filesystem-bound, so move it off the event loop.
            payload["apps"] = await asyncio.to_thread(self._collect_app_ids)
        await self.send_ipc(
            {
                "src": "nsd.menu_watcher",
                "type": "broadcast",
                "action": "apps_changed",
                "payload": payload,
            }
        )
        self.log.info("Broadcast 'apps_changed' sent")

    async def handle_get_apps(self, _payload: dict[str, Any]) -> dict[str, Any]:
        """Return current app ID list for command request-response clients."""
        apps = await asyncio.to_thread(self._collect_app_ids)
        return {"apps": apps, "count": len(apps)}

    async def run(self) -> None:
        """Start watchdog observer and keep plugin alive until shutdown."""
        if Observer is None:
            self.log.error("watchdog dependency is missing; install 'watchdog' to enable MenuWatcherPlugin")
            while True:
                await asyncio.sleep(3600)

        self._loop = asyncio.get_running_loop()
        self.log.info("Starting XDG menu watcher")

        self._observer = Observer()
        handler = MenuEventHandler(self._trigger_reload)

        watched = 0
        for path in self.paths:
            if path.exists() and path.is_dir():
                # Watch only direct directory level; desktop entries are files in this folder.
                self._observer.schedule(handler, str(path), recursive=False)
                watched += 1

        if watched == 0:
            self.log.warning("No existing menu directories to watch")

        self._observer.start()

        try:
            while True:
                await asyncio.sleep(1)
        finally:
            # Cancel pending debounce to prevent late send during shutdown.
            if self._debounce_task and not self._debounce_task.done():
                self._debounce_task.cancel()
            self._observer.stop()
            self._observer.join()