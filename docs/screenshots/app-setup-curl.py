"""Offline curl substitute for the isolated native setup fixture only."""
import json
import os
from pathlib import Path
import re
import sys
import time

args = sys.argv[1:]
control = Path(os.environ["HERDR_APP_HOME"]) / "fixture-response.json"
response = json.loads(control.read_text()) if control.exists() else {}
if response.get("mode") == "slow":
    time.sleep(6)
status = "401" if response.get("mode") == "failure" else "200"
url = args[-1]
if url.endswith("/myself"):
    body = {"accountId": "fictional-native-reader", "active": True}
elif "/comment?" in url:
    body = {"comments": [], "startAt": 0, "maxResults": 100, "total": 0}
elif "/issue/bulkfetch" in url:
    body = {"issues": []}
elif "/issue/" in url:
    key = re.search(r"/issue/(ABC-[0-9]+)", url).group(1)
    body = {"key": key, "fields": {"summary": "Connection setup works inside Herdr",
            "status": {"name": "Open"}, "description": "This issue and account are entirely fictional."}}
else:
    body = {"issues": [], "isLast": True}
if status != "200":
    body = {"errorMessages": ["Fictional authentication failure"]}
output_flag = "--output" if "--output" in args else "-o"
Path(args[args.index(output_flag) + 1]).write_text(json.dumps(body))
sys.stdout.write(status)
