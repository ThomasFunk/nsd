# nsd (Nightshade Daemon)

`nsd` is the central communication hub (server) for the **labwc-Nightshade** desktop environment.
It coordinates plugins and external clients over one local IPC endpoint, so UI tools and helper daemons
can exchange events and commands through a single message bus.

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

`nsd` acts as the IPC server:
- Clients connect to the socket.
- Clients can send commands/events to `nsd`.
- `nsd` broadcasts messages to connected clients.

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

Optional companion config files in the same directory:
- `h-corners.toml` for hot-corner behavior/configuration
- `ld-icons.toml` for desktop icon tool configuration

These files are loaded by `ConfigManager` as additional top-level sections:
- `config.get("h-corners")`
- `config.get("ld-icons")`

Important: these companion files are expected in the **same directory as `nsd.toml`**
(workspace-local or XDG config directory). They are **not** loaded from the
separate external project folders of `h-corners` or `ld-icons`.

Important keys:
- `[global].socket_path`
- `[global].log_level`
- `[modules].*`
- `[automount].blacklist`
- `[labwc_bridge].poll_interval`
- `[labwc_bridge].status_command`
- `[labwc_bridge].close_window_command`
- `[labwc_bridge].switch_workspace_command`
- `[hot_corner_relay].result_broadcast`

Example config is provided in `nsd.toml`.

## IPC Protocol

- **Transport:** Unix Domain Socket
- **Path (default):** `/tmp/nsd.sock`
- **Encoding:** UTF-8
- **Payload format:** JSON objects

For server broadcasts, one JSON message is sent per line (`\n` delimited).
Client implementations in C++, Rust, Go, or other languages can parse the socket stream line-by-line and decode each line as UTF-8 JSON.

## JSON Message Structure

All IPC messages should follow this structure:

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

Field semantics:
- `src`: Message origin (`nsd.automount`, `nsd.labwc_bridge`, `simplewx`, custom client name, ...).
- `type`: Message class (`command` for control requests, `broadcast` for fan-out events, `event` for generic signals).
- `action`: Concrete operation or event name (for example `labwc.switch_workspace`, `mounted`, `show_notification`).
- `payload`: Action-specific JSON object with parameters or result data.

## Generic Python IPC Example (socket + json only)

```python
import socket
import json

SOCKET_PATH = "/tmp/nsd.sock"

msg = {
	"src": "example-client",
	"type": "command",
	"action": "labwc.switch_workspace",
	"payload": {"workspace": "2"},
}

with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
	client.connect(SOCKET_PATH)

	# Send one UTF-8 JSON message.
	client.sendall(json.dumps(msg).encode("utf-8"))

	# Receive and decode incoming UTF-8 JSON messages (newline-delimited stream).
	buffer = ""
	while True:
		chunk = client.recv(4096)
		if not chunk:
			break
		buffer += chunk.decode("utf-8")
		while "\n" in buffer:
			line, buffer = buffer.split("\n", 1)
			line = line.strip()
			if not line:
				continue
			incoming = json.loads(line)
			print("RECV:", incoming)
```

## CLI Test Tool (`nsd-send`)

Path: `tools/nsd-send/nsd-send.py`

Send a command:

```bash
python3 tools/nsd-send/nsd-send.py --action reload
```

Send labwc commands:

```bash
python3 tools/nsd-send/nsd-send.py --type command --action labwc.close_window
python3 tools/nsd-send/nsd-send.py --type command --action labwc.switch_workspace --payload '{"workspace":"2"}'
```

Hot-corner relay command example:

```bash
python3 tools/nsd-send/nsd-send.py --type command --action hotcorner.trigger --payload '{"corner":"top_left","name":"TopLeft","command":"notify-send hotcorner triggered"}'
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

Run unit tests:

```bash
./venv/bin/pip install -r requirements-dev.txt
./venv/bin/python -m pytest -q
```

## Polkit Integration (Automount)

nsd uses `udisksctl` for mounting, which delegates privilege checks to Polkit.
To allow the active console user to mount/unmount without a password prompt,
install the provided rules file:

```bash
sudo cp polkit/90-nsd-automount.rules /etc/polkit-1/rules.d/
sudo chmod 644 /etc/polkit-1/rules.d/90-nsd-automount.rules
```

Requires: polkit ≥ 0.106, udisks2. The rule grants mount/unmount/eject rights
to any active local user in the `users` group — no `sudo` in code needed.

Known current state:
- Automount and notifications are available as plugins, but still evolving.
- No GUI code is included in the daemon itself.