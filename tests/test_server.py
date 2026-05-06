import json

import pytest

from core.server import NightshadeDaemon


class DummyConfig:
    def get(self, section, key):
        if section == "global" and key == "socket_path":
            return "/tmp/nsd-test.sock"
        return None


class FakeWriter:
    def __init__(self, fail_on_drain: bool = False):
        self.fail_on_drain = fail_on_drain
        self.writes = []
        self.closed = False
        self.wait_closed_called = False

    def write(self, data: bytes):
        self.writes.append(data)

    async def drain(self):
        if self.fail_on_drain:
            raise RuntimeError("drain failed")

    def close(self):
        self.closed = True

    async def wait_closed(self):
        self.wait_closed_called = True


class FakeReader:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    async def read(self, _size: int):
        if self._chunks:
            return self._chunks.pop(0)
        return b""


@pytest.mark.asyncio
async def test_broadcast_sends_json_with_newline_and_excludes_sender():
    daemon = NightshadeDaemon(DummyConfig())
    excluded = FakeWriter()
    receiver = FakeWriter()
    daemon.clients = {excluded, receiver}

    payload = {"type": "broadcast", "payload": {"ok": True}}
    await daemon.broadcast(payload, exclude=excluded)

    assert excluded.writes == []
    assert len(receiver.writes) == 1
    assert receiver.writes[0].endswith(b"\n")
    assert json.loads(receiver.writes[0].decode().strip()) == payload


@pytest.mark.asyncio
async def test_broadcast_continues_when_one_client_fails():
    daemon = NightshadeDaemon(DummyConfig())
    broken = FakeWriter(fail_on_drain=True)
    receiver = FakeWriter()
    daemon.clients = {broken, receiver}

    await daemon.broadcast({"type": "broadcast", "value": 1})

    assert len(receiver.writes) == 1


@pytest.mark.asyncio
async def test_process_message_routes_broadcast():
    daemon = NightshadeDaemon(DummyConfig())
    sender = FakeWriter()

    calls = []

    async def fake_broadcast(msg, exclude=None):
        calls.append((msg, exclude))

    daemon.broadcast = fake_broadcast
    msg = {"type": "broadcast", "payload": {"k": "v"}}

    await daemon.process_message(msg, sender)

    assert calls == [(msg, sender)]


@pytest.mark.asyncio
async def test_handle_client_closes_writer_and_removes_client():
    daemon = NightshadeDaemon(DummyConfig())
    reader = FakeReader([b""])
    writer = FakeWriter()

    await daemon.handle_client(reader, writer)

    assert writer.closed is True
    assert writer.wait_closed_called is True
    assert writer not in daemon.clients


@pytest.mark.asyncio
async def test_process_message_dispatches_registered_async_command_handler():
    daemon = NightshadeDaemon(DummyConfig())
    sender = FakeWriter()
    calls = []

    async def handler(payload):
        calls.append(payload)

    daemon.register_command_handler("labwc.switch_workspace", handler)

    await daemon.process_message(
        {
            "type": "command",
            "action": "labwc.switch_workspace",
            "payload": {"workspace": "2"},
        },
        sender,
    )

    assert calls == [{"workspace": "2"}]


@pytest.mark.asyncio
async def test_process_message_ignores_unknown_command_handler():
    daemon = NightshadeDaemon(DummyConfig())
    sender = FakeWriter()

    await daemon.process_message(
        {
            "type": "command",
            "action": "labwc.unknown",
            "payload": {},
        },
        sender,
    )

    assert True


@pytest.mark.asyncio
async def test_process_message_sends_response_for_request_id():
    daemon = NightshadeDaemon(DummyConfig())
    sender = FakeWriter()

    def handler(payload):
        return {"echo": payload.get("value")}

    daemon.register_command_handler("clipboard.get_history", handler)

    await daemon.process_message(
        {
            "type": "command",
            "action": "clipboard.get_history",
            "request_id": "req-1",
            "payload": {"value": 123},
        },
        sender,
    )

    assert len(sender.writes) == 1
    response = json.loads(sender.writes[0].decode().strip())
    assert response["type"] == "response"
    assert response["action"] == "clipboard.get_history"
    assert response["request_id"] == "req-1"
    assert response["payload"] == {"echo": 123}


@pytest.mark.asyncio
async def test_process_message_sends_response_for_expect_response_flag():
    daemon = NightshadeDaemon(DummyConfig())
    sender = FakeWriter()

    async def handler(_payload):
        return {"ok": True}

    daemon.register_command_handler("get_history", handler)

    await daemon.process_message(
        {
            "type": "command",
            "action": "get_history",
            "expect_response": True,
            "payload": {},
        },
        sender,
    )

    assert len(sender.writes) == 1
    response = json.loads(sender.writes[0].decode().strip())
    assert response["type"] == "response"
    assert response["action"] == "get_history"
    assert response["payload"] == {"ok": True}


@pytest.mark.asyncio
async def test_broadcast_dispatches_internal_event_handler():
    daemon = NightshadeDaemon(DummyConfig())
    payloads = []

    async def handler(payload):
        payloads.append(payload)

    daemon.register_event_handler("nsd.menu_watcher:apps_changed", handler)

    await daemon.broadcast(
        {
            "src": "nsd.menu_watcher",
            "type": "broadcast",
            "action": "apps_changed",
            "payload": {"count": 3},
        }
    )

    assert payloads == [{"count": 3}]


@pytest.mark.asyncio
async def test_process_message_routes_event_to_internal_handlers():
    daemon = NightshadeDaemon(DummyConfig())
    sender = FakeWriter()
    payloads = []

    def handler(payload):
        payloads.append(payload)

    daemon.register_event_handler("manual:test", handler)

    await daemon.process_message(
        {
            "src": "manual",
            "type": "event",
            "action": "test",
            "payload": {"ok": True},
        },
        sender,
    )

    assert payloads == [{"ok": True}]
