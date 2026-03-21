import asyncio

import pytest

from modules.menu_watcher import MenuWatcherPlugin


class DummyConfig:
    def __init__(self, watcher_cfg=None):
        self._watcher_cfg = watcher_cfg or {}

    def get(self, section, key=None):
        if key is None and section == "menu_watcher":
            return self._watcher_cfg
        return None


class DummyDaemon:
    def __init__(self):
        self.handlers = {}

    def register_command_handler(self, action, handler):
        self.handlers[action] = handler


@pytest.mark.asyncio
async def test_register_handlers_registers_get_apps_actions():
    async def fake_send_ipc(_msg):
        return None

    plugin = MenuWatcherPlugin(DummyConfig(), fake_send_ipc)
    daemon = DummyDaemon()

    plugin.register_handlers(daemon)

    assert "get_apps" in daemon.handlers
    assert "menu.get_apps" in daemon.handlers


@pytest.mark.asyncio
async def test_handle_get_apps_returns_sorted_list(monkeypatch):
    async def fake_send_ipc(_msg):
        return None

    plugin = MenuWatcherPlugin(DummyConfig(), fake_send_ipc)
    monkeypatch.setattr(plugin, "_collect_app_ids", lambda: ["z.desktop", "a.desktop"])

    result = await plugin.handle_get_apps({})

    assert result["count"] == 2
    assert result["apps"] == ["z.desktop", "a.desktop"]


@pytest.mark.asyncio
async def test_send_update_signal_includes_app_list_when_enabled(monkeypatch):
    sent = []

    async def fake_send_ipc(msg):
        sent.append(msg)

    plugin = MenuWatcherPlugin(DummyConfig({"include_app_list": True}), fake_send_ipc)
    monkeypatch.setattr(plugin, "_collect_app_ids", lambda: ["foo.desktop", "bar.desktop"])

    await plugin._send_update_signal()

    assert sent[-1]["action"] == "apps_changed"
    assert sent[-1]["payload"]["apps"] == ["foo.desktop", "bar.desktop"]


@pytest.mark.asyncio
async def test_schedule_debounce_replaces_previous_task(monkeypatch):
    async def fake_send_ipc(_msg):
        return None

    plugin = MenuWatcherPlugin(DummyConfig(), fake_send_ipc)
    plugin._loop = asyncio.get_running_loop()

    called = []

    async def fake_debounced_emit():
        called.append(True)

    monkeypatch.setattr(plugin, "_debounced_emit", fake_debounced_emit)

    plugin._schedule_debounce()
    first = plugin._debounce_task
    plugin._schedule_debounce()
    second = plugin._debounce_task

    await asyncio.sleep(0)

    assert first is not second
    assert called
