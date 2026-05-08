# nsd (Nightshade Daemon)

[![CI](https://github.com/ThomasFunk/nsd/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/ThomasFunk/nsd/actions/workflows/ci.yml)

`nsd` is the central communication hub (server) for the **Nightshade** desktop environment.
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
- Plugins can subscribe to internal daemon events via `<src>:<action>` keys
	(for example `nsd.menu_watcher:apps_changed`).

Architecture diagrams (yEd `.graphml` format, open with [yEd](https://www.yworks.com/products/yed)):
[docs/architecture/](docs/architecture/) — Start with [Overview.graphml](docs/architecture/Overview.graphml)

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
2. XDG config: `~/.config/nsd/nsd.toml` (or `$XDG_CONFIG_HOME/nsd/nsd.toml`)

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
- `[clipboard].max_items`
- `[clipboard].poll_interval`
- `[menu_watcher].extra_paths`
- `[menu_watcher].debounce_seconds`
- `[menu_watcher].include_app_list`
- `[labwc_bridge].reconfigure_command`
- `[nde_config].base_dir`
- `[nde_config].main_file`
- `[nde_config].output_file`
- `[nde_config].backup`
- `[nde_config].strict_validation`

Example config is provided in `nsd.toml`.

### NDE XML Config Assembly

The optional `nde_config_assembler` module composes a full labwc `rc.xml`
from NDE XML files.

Flow:
- Read main file from `~/.config/nde/config.xml` (or `[nde_config].main_file`).
- Resolve custom XML load directives recursively.
- Merge duplicate top-level blocks (for example multiple `keyboard` blocks).
- Validate generated XML.
- Write atomically to `~/.config/labwc/rc.xml`.
- Emit `nde.reconfigure_result` and trigger `labwc.reconfigure`.

Enable the module:

```toml
[modules]
nde_config_assembler = true
```

Load directive syntax (all are supported):
- `<load path="parts/keyboard.xml"/>`
- `<load file="parts/keyboard.xml"/>`
- `<load href="parts/keyboard.xml"/>`
- `<load>parts/keyboard.xml</load>`

Example main config (`~/.config/nde/config.xml`):

```xml
<labwc_config>
	<keyboard>
		<keybind key="A-W" action="default"/>
	</keyboard>
	<load path="parts/keyboard.xml"/>
	<load path="parts/mouse.xml"/>
</labwc_config>
```

Example part file (`~/.config/nde/parts/keyboard.xml`):

```xml
<keyboard>
	<keybind key="A-W" action="override"/>
	<keybind key="A-Return" action="terminal"/>
</keyboard>
```

Security/safety rules:
- Only files below `~/.config/nde` are allowed.
- Absolute load paths are rejected.
- `..` path traversal is rejected.
- Load cycles are detected and rejected.

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

### Command Request-Response (direct reply)

`nsd` supports direct responses for command messages when either
- `request_id` is present, or
- `expect_response` is set to `true`.

Example request:

```json
{
	"src": "clipboard-viewer",
	"type": "command",
	"action": "get_history",
	"request_id": "req-42",
	"payload": {}
}
```

Example direct response (to the same client connection):

```json
{
	"src": "nsd.server",
	"type": "response",
	"action": "get_history",
	"request_id": "req-42",
	"payload": {
		"items": ["foo", "bar"],
		"count": 2
	}
}
```

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

Clipboard commands:

```bash
python3 tools/nsd-send/nsd-send.py --type command --action get_history
python3 tools/nsd-send/nsd-send.py --type command --action clear
```

Clipboard plugin behavior:
- `nsd` keeps an in-memory clipboard history (newest first).
- history size is limited by `[clipboard].max_items` (for example `50`).
- viewers can request history via `get_history` / `clipboard.get_history`.
- clearing is supported via `clear` / `clipboard.clear`.

Menu watcher behavior:
- watches application directories for `.desktop` file changes
- debounces bursts of file events before broadcasting `apps_changed`
- can optionally include current app IDs in payload (`include_app_list = true`)
- supports command-based app list query via `get_apps` / `menu.get_apps`

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

Optional Wayland smoke test (requires active Wayland session and `labwc` in `PATH`):

```bash
./venv/bin/python -m pytest -q -m wayland
```

CI setup:
- GitHub Actions workflow: `.github/workflows/ci.yml`
- Default job runs full test suite on `ubuntu-latest`.
- Optional Wayland smoke job is manual (`workflow_dispatch` + `run_wayland=true`) and
	expects a self-hosted runner labeled `linux`, `wayland`.
- Runner setup details: `.github/README-ci.md`

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