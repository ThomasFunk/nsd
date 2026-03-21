__author__ = 'Thomas Funk'
__coauthors__ = 'Github Copilot & Gemini'
__date__ = "2026/03/21"

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("nsd.server")

class NightshadeDaemon:
    def __init__(self, config: Any):
        self.config = config
        self.clients: set[asyncio.StreamWriter] = set()
        self.socket_path = Path(self.config.get("global", "socket_path") or "/tmp/nsd.sock")

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
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
                    
                    # Logik-Verteilung
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
        message_bytes = json.dumps(msg).encode() + b'\n'
        for client in list(self.clients):
            if exclude is not None and client == exclude:
                continue
            try:
                client.write(message_bytes)
                await client.drain()
            except Exception as exc:
                log.warning("Broadcast to client failed: %s", exc)

    async def process_message(self, msg: dict[str, Any], sender_writer: asyncio.StreamWriter) -> None:
        """Hier passiert die Magie: Routing & Aktionen"""
        msg_type = msg.get("type")
        
        # Beispiel: System-weite Benachrichtigung (Broadcast)
        if msg_type == "broadcast":
            await self.broadcast(msg, exclude=sender_writer)
        
        # Beispiel: Internes Kommando für den Daemon (z.B. Mount)
        elif msg_type == "command":
            action = msg.get("action")
            log.info("Executing action: %s", action)
            # Hier käme der Aufruf für udisks2 / mounting hin

    async def run(self) -> None:
        # Socket aufräumen, falls er noch existiert
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