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
