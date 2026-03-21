import asyncio
from modules.base import BasePlugin
from dbus_next.aio import MessageBus
from dbus_next.service import ServiceInterface, method, dbus_property
from dbus_next import BusType

class NotificationService(ServiceInterface):
    def __init__(self, name, send_ipc_func):
        super().__init__(name)
        self.send_ipc = send_ipc_func

    @method()
    async def Notify(self, app_name: 's', replaces_id: 'u', app_icon: 's', 
                     summary: 's', body: 's', actions: 'as', hints: 'a{sv}', expire_timeout: 'i') -> 'u':
        
        # Die DBus-Nachricht in unser LNS-JSON Format umwandeln
        msg = {
            "src": "nsd.notifications",
            "type": "broadcast",
            "action": "show_notification",
            "payload": {
                "app": app_name,
                "title": summary,
                "message": body,
                "icon": app_icon,
                "timeout": expire_timeout
            }
        }
        
        # Per IPC an alle (z.B. SimpleWx UI) senden
        asyncio.create_task(self.send_ipc(msg))
        
        return 42 # Eine ID für die Notification zurückgeben

class NotificationsPlugin(BasePlugin):
    async def run(self):
        bus = await MessageBus(bus_type=BusType.SESSION).connect()
        interface = NotificationService('org.freedesktop.Notifications', self.send_ipc)
        bus.export('/org/freedesktop/Notifications', interface)
        
        await bus.request_name('org.freedesktop.Notifications')
        print("[Notifications] DBus-Interface registriert.")
        
        # Plugin am Leben halten
        while True:
            await asyncio.sleep(3600)