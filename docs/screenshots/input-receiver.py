#!/usr/bin/env python3
"""Harmless raw terminal receiver for the isolated fictional review app."""
import json
import os
from pathlib import Path
import select
import sys
import termios
import time
import tty

home = Path(os.environ["HERDR_APP_HOME"])
original = termios.tcgetattr(sys.stdin.fileno())
last = ""
try:
    tty.setraw(sys.stdin.fileno())
    (home / "fixture-receiver-ready").touch()
    with (home / "fixture-terminal-input.bin").open("ab", buffering=0) as received:
        deadline = time.monotonic() + 3600
        while time.monotonic() < deadline:
            if select.select([sys.stdin], [], [], .1)[0]:
                data = os.read(sys.stdin.fileno(), 4096)
                if not data:
                    break
                received.write(data)
            discovery = home / "fixture-discovery"
            if discovery.exists():
                key = discovery.read_text()
                if key != last:
                    if key.startswith("{"):
                        activity = json.loads(key)
                        if activity.get("reset"):
                            print("\033[2J\033[H", end="")
                        shown = " ".join(activity["keys"])
                    else:
                        shown = key
                    print(f"\r\n{shown} fictional discovered issue\r", flush=True)
                    last = key
finally:
    termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, original)
