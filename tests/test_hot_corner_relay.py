import pytest

from modules.hot_corner_relay import HotCornerRelayPlugin


class DummyConfig:
    def __init__(self, relay_cfg=None):
        self._relay_cfg = relay_cfg or {}

    def get(self, section, key=None):
        if key is None and section == "hot_corner_relay":
            return self._relay_cfg
        return None


class DummyDaemon:
    def __init__(self):
        self.handlers = {}

    def register_command_handler(self, action, handler):
        self.handlers[action] = handler


@pytest.mark.asyncio
async def test_register_handlers_registers_hotcorner_action():
    async def fake_send_ipc(_msg):
        return None

    plugin = HotCornerRelayPlugin(DummyConfig(), fake_send_ipc)
    daemon = DummyDaemon()

    plugin.register_handlers(daemon)

    assert "hotcorner.trigger" in daemon.handlers


@pytest.mark.asyncio
async def test_handle_trigger_broadcasts_missing_command_error():
    sent = []

    async def fake_send_ipc(msg):
        sent.append(msg)

    plugin = HotCornerRelayPlugin(DummyConfig(), fake_send_ipc)

    await plugin.handle_trigger({"corner": "top_left", "name": "TopLeft"})

    assert sent[-1]["action"] == "hotcorner.command_result"
    assert sent[-1]["payload"]["ok"] is False
    assert sent[-1]["payload"]["stderr"] == "missing command"


@pytest.mark.asyncio
async def test_handle_trigger_executes_command_and_broadcasts_result(monkeypatch):
    sent = []

    async def fake_send_ipc(msg):
        sent.append(msg)

    plugin = HotCornerRelayPlugin(DummyConfig(), fake_send_ipc)
    monkeypatch.setattr(plugin, "_run_command", lambda command: (0, f"ran:{command}", ""))

    await plugin.handle_trigger({"corner": "bottom_right", "name": "BottomRight", "command": "echo hi"})

    assert sent[-1]["payload"]["ok"] is True
    assert sent[-1]["payload"]["command"] == "echo hi"
    assert sent[-1]["payload"]["stdout"] == "ran:echo hi"
