# GitHub Copilot Instructions for **nsd** (Nightshade Daemon)

## 🎯 Project Context
You are an expert in Python 3 and Linux system programming. We are developing **nsd**, a central, modular background service for the **labwc-Nightshade** desktop environment. The daemon acts as a communication hub, hardware monitor (automounting), and bridge between various specialized desktop tools.

## 🏛️ Architectural Principles
1. **Asynchronous Core:** The daemon must use `asyncio`. All I/O operations (sockets, file watching, DBus) must be non-blocking.
2. **Strict Plugin System:** All features (Mounting, Notifications, Labwc-Bridge) must be implemented as plugins in the `modules/` directory.
3. **Class Inheritance:** Every plugin **must** inherit from `modules.base.BasePlugin`.
4. **Decoupled Communication:** The daemon communicates with external tools (SimpleWx, h-corners, ld-icons) exclusively via **Unix Domain Sockets** (`/tmp/nsd.sock`) using **JSON packets**.
5. **No GUI Logic:** The daemon is a CLI/System service. It must **not** import GUI libraries (Qt, GTK, SimpleWx). It only sends events for other tools to visualize.

## 💻 Code Standards & Patterns
- **Type Hinting:** Use strict type hints for all function signatures and variables.
- **Configuration:** Always use the `ConfigManager` instance. Never hardcode paths, socket names, or threshold values.
- **Path Management:** Use `pathlib.Path` instead of `os.path`.
- **Hardware Access:** Use `pyudev` for device monitoring and `udisksctl` (via `subprocess`) for mounting to leverage PolicyKit.
- **Async Safety:** Use `asyncio.to_thread` for blocking legacy calls (like `pyudev` monitoring loops) to keep the main event loop responsive.

## 📡 JSON Protocol Standard
All IPC messages must follow this structure:
```json
{
  "src": "plugin-name",
  "type": "broadcast | command | event",
  "action": "specific_action_name",
  "payload": { 
    "key": "value" 
  }
}
```

## 🚫 Strictly Forbidden
- **NO `sudo`:** Never use `sudo` in code. Use DBus or `udisksctl` to trigger privileged actions via Polkit.
- **NO `time.sleep()`:** Always use `await asyncio.sleep()` to prevent blocking the daemon.
- **NO direct UI imports:** Do not include any code that requires an X11 or Wayland display connection within the daemon core.
- **NO manual fstab parsing:** Use `pyudev` or `udisks2` for partition management.

## 🛠️ Plugin Template Example
When asked to create a new module, follow this pattern:

```python
from modules.base import BasePlugin
import asyncio
import logging

class NewFeaturePlugin(BasePlugin):
    async def run(self) -> None:
        logging.info(f"[{self.name}] Plugin started.")
        while True:
            # Implementation of the async loop
            await asyncio.sleep(10)
            
    async def some_action(self):
        # Example of sending an IPC message
        await self.send_ipc({
            "src": self.name.lower(),
            "type": "event",
            "action": "status_update",
            "payload": {"active": True}
        })
```

## 📂 Expected Project Structure
The daemon must follow this layout to work with the `PluginLoader`:
- `nsd.py` (Entry point)
- `core/` (Config, Server, Loader)
- `modules/` (Plugins inheriting from `BasePlugin`)

## 🛠️ Testing & Development
- **Manual Testing:** Use `socat` or the `nsd-send` tool to send raw JSON to `/tmp/nsd.sock`.
- **Hot Reloading:** The `ConfigManager` should be re-initialized upon receiving a `SIGHUP` signal.
- **Log Monitoring:** All modules should use `logging` so that output can be piped to a central log file or `journalctl`.