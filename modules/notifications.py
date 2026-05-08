__author__ = 'Thomas Funk'
__coauthors__ = 'Github Copilot & Gemini'
__date__ = "2026/03/21"

"""DBus notification bridge plugin for nsd."""

# pyright: reportUndefinedVariable=false, reportInvalidTypeForm=false

import asyncio
from modules.base import BasePlugin
from dbus_next.aio import MessageBus
from dbus_next.service import ServiceInterface, method
from dbus_next import BusType

DBUS_S = "s"
DBUS_U = "u"
DBUS_AS = "as"
DBUS_A_SV = "a{sv}"
DBUS_I = "i"

class NotificationService(ServiceInterface):
    """DBus notification service forwarding events to NSD IPC."""

    def __init__(self, name, send_ipc_func):
        """Initialize DBus service wrapper.

        Parameters
        ----------
        name : str
            DBus interface name.
        send_ipc_func : callable
            Async callback used to forward notifications to IPC.
        """
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
        """Build standardized NSD IPC payload for one notification.

        Parameters
        ----------
        app_name : str
            Application name.
        app_icon : str
            Application icon identifier/path.
        summary : str
            Notification title.
        body : str
            Notification message body.
        expire_timeout : int
            Expiration timeout in milliseconds.

        Returns
        -------
        dict
            IPC message dictionary.
        """
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
    def Notify(
        self,
        app_name: DBUS_S,
        replaces_id: DBUS_U,
        app_icon: DBUS_S,
        summary: DBUS_S,
        body: DBUS_S,
        actions: DBUS_AS,
        hints: DBUS_A_SV,
        expire_timeout: DBUS_I,
    ) -> DBUS_U:
        """Translate DBus ``Notify`` calls into NSD broadcasts.

        Parameters
        ----------
        app_name : DBUS_S
            Calling application name.
        replaces_id : DBUS_U
            Existing notification ID to replace, if any.
        app_icon : DBUS_S
            Application icon identifier/path.
        summary : DBUS_S
            Notification title.
        body : DBUS_S
            Notification body text.
        actions : DBUS_AS
            DBus actions array (currently unused).
        hints : DBUS_A_SV
            DBus hints map (currently unused).
        expire_timeout : DBUS_I
            Timeout in milliseconds.

        Returns
        -------
        DBUS_U
            Notification ID expected by DBus clients.
        """

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
    """Plugin that registers the DBus notification service."""

    async def run(self) -> None:
        """Connect session bus, export interface, and keep service alive.

        Returns
        -------
        None
        """
        bus = await MessageBus(bus_type=BusType.SESSION).connect()
        interface = NotificationService('org.freedesktop.Notifications', self.send_ipc)
        bus.export('/org/freedesktop/Notifications', interface)
        
        await bus.request_name('org.freedesktop.Notifications')
        self.log.info("DBus interface registered: org.freedesktop.Notifications")
        
        # Keep plugin task alive.
        while True:
            await asyncio.sleep(3600)