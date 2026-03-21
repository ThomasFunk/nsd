# Roadmap: nsd (Nightshade Daemon)
This project is the central service hub for the labwc-Nightshade desktop environment.
It is modular, communicates via JSON packets over Unix Domain Sockets, and is fully written in Python 3.

# Phase 1: Core & Infrastructure (Priority: Blocking)
- [x] Configuration system: Implement ConfigManager:
    - [x] TOML support
    - [x] Defaults
    - [x] nsd command-line option -d|--debug
    - [x] Set XDG path logic: local path ${workspaceFolder}/ preferred; default XDG path ~/.config/lns/

- [x] IPC server: Asyncio-based Unix Domain Socket server (/tmp/nsd.sock).
- [x] Plugin loader: Dynamic loading of modules from modules/ that inherit from BasePlugin.
- [x] Logging: Centralized log output for all plugins and the core.

# Phase 2: System Services & Hardware (Priority: High)
- [x] Automount-Plugin:
    - [x] Integrate pyudev for hardware events.
    - [x] Trigger udisksctl for passwordless mounting.
    - [x] Broadcast mounted/unmounted events to the socket.
- [x] Polkit integration: Create and document .rules for privileged actions without password prompts.
- [x] Desktop sync: Ensure ld-icons can process mount events immediately.

# Phase 3: Desktop Integration (Priority: Medium)
- [x] Notification server:
    - [x] Register on DBus (org.freedesktop.Notifications).
    - [x] Convert DBus signals into nsd JSON packets for display in SimpleWx.
- [x] Extend simpleWx with IPC client functionality - base functions enable_nsd und nsd_send are available but have to be checked for propper work. Hint: don't switch to asyncio because wx has issues with it.
- [x] Labwc-Bridge:
    - [x] Implement an interface for remote control of labwc (close windows, switch workspaces).
    - [x] Monitor labwc status changes.
- [x] Hot-corner relay: Receive signals from h-corners and execute configured commands.

# Phase 4: Tools & Stabilization (Priority: Low)
- [x] Unit tests: Add pytest-based tests for configuration, IPC server, plugin loader, and nsd entrypoint wiring.
- [ ] nsd-send CLI: Small Python tool to manually send JSON commands to the socket (for shell scripts).
- [ ] Hot reload: Implement SIGHUP to reload TOML configuration without process restart.
- [ ] Auto-discovery: Plugins should detect at runtime which other LNS tools (such as wbar) are currently active.