__author__ = 'Thomas Funk'
__coauthors__ = 'Github Copilot & Gemini'
__date__ = "2026/03/21"

"""Async Unix Domain Socket server used by nsd for JSON IPC."""

import asyncio
import inspect
import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("nsd.server")

class NightshadeDaemon:
    """Handle IPC client connections, message routing, and broadcasting."""

    def __init__(self, config: Any):
        """Initialize daemon state from the provided configuration object."""
        self.config = config
        self.clients: set[asyncio.StreamWriter] = set()
        self.command_handlers: dict[str, Any] = {}
        self.socket_path = Path(self.config.get("global", "socket_path") or "/tmp/nsd.sock")

    def register_command_handler(self, action: str, handler: Any) -> None:
        """Register one IPC command handler for a specific action string."""
        self.command_handlers[action] = handler
        log.info("Registered command handler: %s", action)

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Read messages from a client until disconnect and process them."""
        self.clients.add(writer)
        log.info("New connection")

        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                
                try:
                    message = json.loads(data.decode())
                    log.debug("Message received: %s", message)
                    
                    # Route and process the parsed message.
                    await self.process_message(message, writer)
                    
                except json.JSONDecodeError:
                    log.warning("Invalid JSON received")

        except Exception as e:
            log.error("Error in client loop: %s", e)
        finally:
            log.info("Connection closed")
            self.clients.remove(writer)
            writer.close()
            await writer.wait_closed()

    async def broadcast(self, msg: dict[str, Any], exclude: asyncio.StreamWriter | None = None) -> None:
        """Send one JSON message to all connected clients.

        Args:
            msg: JSON-serializable message dictionary.
            exclude: Optional client to skip (typically the sender).
        """
        message_bytes = json.dumps(msg).encode() + b'\n'
        for client in list(self.clients):
            if exclude is not None and client == exclude:
                continue
            try:
                client.write(message_bytes)
                await client.drain()
            except Exception as exc:
                log.warning("Broadcast to client failed: %s", exc)

    async def send_to_client(self, writer: asyncio.StreamWriter, msg: dict[str, Any]) -> None:
        """Send one JSON message to exactly one connected client."""
        try:
            writer.write(json.dumps(msg).encode() + b'\n')
            await writer.drain()
        except Exception as exc:
            log.warning("Direct reply to client failed: %s", exc)

    async def process_message(self, msg: dict[str, Any], sender_writer: asyncio.StreamWriter) -> None:
        """Route incoming messages based on their `type` field."""
        msg_type = msg.get("type")
        
        # Forward broadcast messages to all clients except the sender.
        if msg_type == "broadcast":
            await self.broadcast(msg, exclude=sender_writer)
        
        # Handle daemon-internal commands.
        elif msg_type == "command":
            action = msg.get("action")
            log.info("Executing action: %s", action)
            if not action:
                log.warning("Command message missing action field")
                return
            handler = self.command_handlers.get(action)
            if handler is None:
                log.warning("No handler registered for action: %s", action)
                return
            payload = msg.get("payload", {})
            request_id = msg.get("request_id")
            expects_response = bool(request_id is not None or msg.get("expect_response", False))
            result = handler(payload)
            if inspect.isawaitable(result):
                result = await result

            if expects_response:
                response_payload = result if isinstance(result, dict) else {"result": result}
                await self.send_to_client(
                    sender_writer,
                    {
                        "src": "nsd.server",
                        "type": "response",
                        "action": action,
                        "request_id": request_id,
                        "payload": response_payload,
                    },
                )

    async def run(self) -> None:
        """Start the Unix socket server and serve forever."""
        # Remove stale socket file from previous daemon runs.
        if self.socket_path.exists():
            self.socket_path.unlink()

        server = await asyncio.start_unix_server(self.handle_client, path=str(self.socket_path))
        log.info("Nightshade Daemon listening on %s", self.socket_path)

        async with server:
            await server.serve_forever()

if __name__ == "__main__":
    from core.config import ConfigManager

    daemon = NightshadeDaemon(ConfigManager())
    try:
        asyncio.run(daemon.run())
    except KeyboardInterrupt:
        pass