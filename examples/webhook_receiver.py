#!/usr/bin/env python3
"""Minimal Oura webhook receiver — example starting point, not production code.

Oura verifies your callback URL with a GET request when you create the
subscription, then POSTs event notifications as JSON. This server logs
everything it receives and answers 200.

Event payloads carry a *reference* (data_type + object id + user id), not the
full record — use ./bin/oura to fetch the actual data when an event arrives.

Run behind public HTTPS (Oura requires it), then:
    ./bin/oura webhook create --callback-url https://your.host/oura-webhook \
        --event-type create --data-type daily_sleep

Usage: python3 webhook_receiver.py [port]
"""

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs


class Handler(BaseHTTPRequestHandler):
    def _ok(self, body=b"ok"):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        # Oura's verification challenge at subscription time.
        q = parse_qs(urlparse(self.path).query)
        print("VERIFY GET %s query=%s" % (self.path, q), flush=True)
        challenge = q.get("challenge", [None])[0]
        self._ok(challenge.encode() if challenge else b"ok")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8", "ignore")
        try:
            event = json.loads(raw)
        except Exception:
            event = {"_raw": raw[:500]}
        print("EVENT %s" % json.dumps(event), flush=True)
        # TODO: fetch the referenced record with ./bin/oura and ingest it.
        self._ok()

    def log_message(self, *a):
        pass  # keep stdout for events only


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
    print("listening on :%d" % port, flush=True)
