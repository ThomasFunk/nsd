import asyncio

import pytest

from modules.notifications import NotificationService


@pytest.mark.asyncio
async def test_notify_schedules_ipc_message(monkeypatch):
    sent_messages = []
    scheduled = []
    original_create_task = asyncio.create_task

    async def fake_send_ipc(msg):
        sent_messages.append(msg)

    async def _drain(coro):
        await coro

    def fake_create_task(coro):
        task = original_create_task(_drain(coro))
        scheduled.append(task)
        return task

    monkeypatch.setattr("modules.notifications.asyncio.create_task", fake_create_task)

    service = NotificationService("org.freedesktop.Notifications", fake_send_ipc)
    notification_id = await service.Notify.__wrapped__(
        service,
        "demo-app",
        0,
        "dialog-information",
        "Hello",
        "World",
        [],
        {},
        2500,
    )

    await asyncio.gather(*scheduled)

    assert notification_id == 1
    assert sent_messages == [
        {
            "src": "nsd.notifications",
            "type": "broadcast",
            "action": "show_notification",
            "payload": {
                "app": "demo-app",
                "title": "Hello",
                "message": "World",
                "icon": "dialog-information",
                "timeout": 2500,
            },
        }
    ]


@pytest.mark.asyncio
async def test_notify_reuses_replaces_id_when_provided(monkeypatch):
    original_create_task = asyncio.create_task
    monkeypatch.setattr("modules.notifications.asyncio.create_task", lambda coro: original_create_task(coro))

    service = NotificationService("org.freedesktop.Notifications", lambda _msg: asyncio.sleep(0))
    notification_id = await service.Notify.__wrapped__(
        service,
        "demo-app",
        77,
        "dialog-information",
        "Hello",
        "World",
        [],
        {},
        -1,
    )

    assert notification_id == 77
