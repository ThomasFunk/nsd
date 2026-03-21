import pytest

from modules.labwc_bridge import LabwcBridgePlugin


class DummyConfig:
    def __init__(self, bridge_cfg=None):
        self._bridge_cfg = bridge_cfg or {}

    def get(self, section, key=None):
        if key is None:
            if section == "labwc_bridge":
                return self._bridge_cfg
            return {}
        return None


class DummyDaemon:
    def __init__(self):
        self.handlers = {}

    def register_command_handler(self, action, handler):
        self.handlers[action] = handler


@pytest.mark.asyncio
async def test_register_handlers_registers_expected_actions():
    async def fake_send_ipc(_msg):
        return None

    plugin = LabwcBridgePlugin(DummyConfig(), fake_send_ipc)
    daemon = DummyDaemon()

    plugin.register_handlers(daemon)

    assert "labwc.close_window" in daemon.handlers
    assert "labwc.switch_workspace" in daemon.handlers


@pytest.mark.asyncio
async def test_handle_switch_workspace_reports_missing_workspace():
    sent = []

    async def fake_send_ipc(msg):
        sent.append(msg)

    plugin = LabwcBridgePlugin(DummyConfig(), fake_send_ipc)

    await plugin.handle_switch_workspace({})

    assert sent[-1]["action"] == "labwc_command_result"
    assert sent[-1]["payload"]["ok"] is False
    assert sent[-1]["payload"]["stderr"] == "missing workspace"


@pytest.mark.asyncio
async def test_handle_switch_workspace_executes_formatted_command(monkeypatch):
    sent = []

    async def fake_send_ipc(msg):
        sent.append(msg)

    plugin = LabwcBridgePlugin(DummyConfig(), fake_send_ipc)

    def fake_run_command(command):
        assert command.endswith("workspace 3")
        return 0, "ok", ""

    monkeypatch.setattr(plugin, "_run_command", fake_run_command)

    await plugin.handle_switch_workspace({"workspace": "3"})

    assert sent[-1]["payload"]["ok"] is True
    assert sent[-1]["payload"]["workspace"] == "3"


@pytest.mark.asyncio
async def test_poll_status_broadcasts_only_on_change(monkeypatch):
    sent = []

    async def fake_send_ipc(msg):
        sent.append(msg)

    plugin = LabwcBridgePlugin(DummyConfig(), fake_send_ipc)
    outputs = [
        (0, '{"ws":1}', ""),
        (0, '{"ws":1}', ""),
        (0, '{"ws":2}', ""),
    ]

    def fake_run_command(_command):
        return outputs.pop(0)

    monkeypatch.setattr(plugin, "_run_command", fake_run_command)

    await plugin._poll_status_once()
    await plugin._poll_status_once()
    await plugin._poll_status_once()

    status_msgs = [m for m in sent if m.get("action") == "labwc.status_changed"]
    assert len(status_msgs) == 2
    assert status_msgs[0]["payload"]["data"] == {"ws": 1}
    assert status_msgs[1]["payload"]["data"] == {"ws": 2}
