__author__ = 'Thomas Funk'
__coauthors__ = 'Github Copilot & Gemini'
__date__ = "2026/03/21"

"""DBus notification bridge plugin for nsd."""

import asyncio
from modules.base import BasePlugin
from dbus_next.aio import MessageBus
from dbus_next.service import ServiceInterface, method
from dbus_next import BusType

class NotificationService(ServiceInterface):
    """Expose org.freedesktop.Notifications and forward events to IPC."""

    def __init__(self, name, send_ipc_func):
        """Store IPC callback used to broadcast notification events."""
        super().__init__(name)
        self.send_ipc = send_ipc_func
        self._next_notification_id = 1

    def _build_ipc_message(
        self,
        app_name: str,
        app_icon: str,
        summary: str,
        body: str,
        expire_timeout: int,
    ) -> dict:
        """Build the standardized nsd IPC payload for one notification."""
        return {
            "src": "nsd.notifications",
            "type": "broadcast",
            "action": "show_notification",
            "payload": {
                "app": app_name,
                "title": summary,
                "message": body,
                "icon": app_icon,
                "timeout": expire_timeout,
            },
        }

    @method()
    async def Notify(self, app_name: 's', replaces_id: 'u', app_icon: 's', 
                     summary: 's', body: 's', actions: 'as', hints: 'a{sv}', expire_timeout: 'i') -> 'u':
        """Translate DBus notification calls into nsd JSON broadcasts."""

        # Convert the DBus payload into the nsd JSON event format.
        msg = self._build_ipc_message(app_name, app_icon, summary, body, expire_timeout)
        
        # Broadcast to all connected IPC clients (e.g. UI components).
        asyncio.create_task(self.send_ipc(msg))

        # Return a stable incremental ID as expected by the DBus API.
        if replaces_id > 0:
            return replaces_id
        notification_id = self._next_notification_id
        self._next_notification_id += 1
        return notification_id

class NotificationsPlugin(BasePlugin):
    """Register the DBus notification service and keep it running."""

    async def run(self) -> None:
        """Connect to session bus, export interface, and stay alive."""
        bus = await MessageBus(bus_type=BusType.SESSION).connect()
        interface = NotificationService('org.freedesktop.Notifications', self.send_ipc)
        bus.export('/org/freedesktop/Notifications', interface)
        
        await bus.request_name('org.freedesktop.Notifications')
        self.log.info("DBus interface registered: org.freedesktop.Notifications")
        
        # Keep plugin task alive.
        while True:
            await asyncio.sleep(3600)