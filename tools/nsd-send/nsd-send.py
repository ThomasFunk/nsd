#!/usr/bin/env python3

__author__ = 'Thomas Funk'
__coauthors__ = 'Github Copilot & Gemini'
__date__ = "2026/03/20"
__version__ = "0.1.0"

import socket
import json
import sys
import argparse

SOCKET_PATH = "/tmp/nsd.sock"
def send_message(msg_dict: dict):
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.connect(SOCKET_PATH)
            message = json.dumps(msg_dict).encode('utf-8')
            client.sendall(message)
            print(f"[✔] Gesendet: {msg_dict}")
    except FileNotFoundError:
        print(f"[✘] Fehler: Socket {SOCKET_PATH} nicht gefunden. Läuft der nsd?")
    except Exception as e:
        print(f"[✘] Fehler: {e}")

def main():
    parser = argparse.ArgumentParser(description="LNS Daemon Client Tool")
    parser.add_argument("--type", default="command", help="Typ der Nachricht (command/broadcast/event)")
    parser.add_argument("--action", help="Die auszuführende Aktion (z.B. reload, notify)")
    parser.add_argument("--payload", help="JSON-String für zusätzliche Daten", default="{}")
    parser.add_argument("--raw", help="Sendet einen kompletten JSON-String")

    args = parser.parse_args()

    if args.raw:
        try:
            msg = json.loads(args.raw)
            send_message(msg)
        except json.JSONDecodeError:
            print("[✘] Ungültiges JSON im --raw Argument")
            return
    elif args.action:
        try:
            payload = json.loads(args.payload)
            msg = {
                "src": "nsd-send",
                "type": args.type,
                "action": args.action,
                "payload": payload
            }
            send_message(msg)
        except:
            parser.print_help()

if __name__ == "__main__":
    main()