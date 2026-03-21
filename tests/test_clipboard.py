import pytest

from modules.clipboard import ClipboardPlugin


class DummyConfig:
    def __init__(self, clipboard_cfg=None):
        self._clipboard_cfg = clipboard_cfg or {}

    def get(self, section, key=None):
        if key is None and section == "clipboard":
            return self._clipboard_cfg
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

    plugin = ClipboardPlugin(DummyConfig(), fake_send_ipc)
    daemon = DummyDaemon()

    plugin.register_handlers(daemon)

    assert "get_history" in daemon.handlers
    assert "clipboard.get_history" in daemon.handlers
    assert "clear" in daemon.handlers
    assert "clipboard.clear" in daemon.handlers


@pytest.mark.asyncio
async def test_check_clipboard_adds_unique_entries_and_respects_max_items(monkeypatch):
    sent = []

    async def fake_send_ipc(msg):
        sent.append(msg)

    plugin = ClipboardPlugin(DummyConfig({"max_items": 2}), fake_send_ipc)

    values = iter(["one", "one", "two", "three"])
    monkeypatch.setattr(plugin, "_read_clipboard_text", lambda: next(values, ""))

    await plugin._check_clipboard()
    await plugin._check_clipboard()
    await plugin._check_clipboard()
    await plugin._check_clipboard()

    assert plugin.history == ["three", "two"]
    assert sent[-1]["action"] == "clipboard.history_updated"
    assert sent[-1]["payload"]["count"] == 2


@pytest.mark.asyncio
async def test_get_history_and_clear_return_state():
    async def fake_send_ipc(_msg):
        return None

    plugin = ClipboardPlugin(DummyConfig(), fake_send_ipc)
    plugin.history = ["b", "a"]

    history_result = await plugin.handle_get_history({})
    clear_result = await plugin.handle_clear_history({})

    assert history_result["items"] == ["b", "a"]
    assert history_result["count"] == 2
    assert clear_result["status"] == "cleared"
    assert clear_result["count"] == 0
    assert plugin.history == []
