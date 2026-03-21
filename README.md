# nsd (Nightshade Daemon)

`nsd` is the central service hub for the **labwc-Nightshade** desktop environment.
It provides modular background services and IPC communication via **Unix Domain Sockets** using **JSON packets**.

## Status

The project is under active development.
Phase 1 (Core & Infrastructure) is implemented:
- Config manager with TOML + defaults
- Async Unix socket IPC server
- Dynamic plugin loader
- Centralized logging

See [Roadmap.md](Roadmap.md) for details.

## Core Architecture

- **Entry point:** `nsd.py`
- **Core components:** `core/config.py`, `core/server.py`, `core/plugin_loader.py`
- **Plugins:** `modules/` (all plugins must inherit from `modules/base.py::BasePlugin`)
- **IPC transport:** Unix Domain Socket (default: `/tmp/nsd.sock`)

## Requirements

- Python 3.11+
- `venv` + `pip`
- Linux user session DBus (for notifications plugin)
- `udisksctl` (for automount flows)

Python dependencies:
- `pyudev`
- `dbus-next`

## Installation

```bash
cd ~/workset/nsd
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Run

Normal mode:

```bash
./venv/bin/python nsd.py
```

Debug mode:

```bash
./venv/bin/python nsd.py --debug
```

## Configuration

Default config file name: `nsd.toml`

Resolution order:
1. Workspace-local config: `<workspace>/nsd.toml`
2. XDG config: `~/.config/lns/nsd.toml` (or `$XDG_CONFIG_HOME/lns/nsd.toml`)

Important keys:
- `[global].socket_path`
- `[global].log_level`
- `[modules].*`
- `[automount].blacklist`

Example config is provided in `nsd.toml`.

## IPC JSON Message Format

All messages should follow this structure:

```json
{
	"src": "plugin-or-client",
	"type": "broadcast | command | event",
	"action": "action_name",
	"payload": {
		"key": "value"
	}
}
```

## CLI Test Tool (`nsd-send`)

Path: `tools/nsd-send/nsd-send.py`

Send a command:

```bash
python3 tools/nsd-send/nsd-send.py --action reload
```

Send a broadcast with payload:

```bash
python3 tools/nsd-send/nsd-send.py --type broadcast --action notify --payload '{"title":"Test","msg":"Hello from shell"}'
```

Send raw JSON:

```bash
python3 tools/nsd-send/nsd-send.py --raw '{"src":"manual","type":"command","action":"reload","payload":{}}'
```

## Development Notes

Quick syntax checks:

```bash
./venv/bin/python -m py_compile nsd.py core/*.py modules/*.py tools/nsd-send/nsd-send.py
```

Known current state:
- Automount and notifications are available as plugins, but still evolving.
- No GUI code is included in the daemon itself.