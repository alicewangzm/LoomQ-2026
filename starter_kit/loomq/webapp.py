#!/usr/bin/env python3
"""LoomQ web UI - the L2 zero-background-user entry point.

A tiny stdlib web server (no third-party deps) that wraps the L2 agent and the
L1 runtime so a non-expert can, in one page: describe what they want in plain
words, see the circuit the agent writes, RUN it on a local simulator, and see
the results as a chart.

Run (with LOOMQ_LLM_* set, from the repo's .venv so the simulators are present):

    python starter_kit/loomq/webapp.py

Then open http://localhost:8000

Endpoints:
    GET  /            -> the single-page UI (index.html beside this file)
    POST /api/chat    -> {"prompt": str}          -> {"reply": str, "qasm": str|null}
    POST /api/run     -> {"qasm": str, "shots"?}  -> {"counts": {...}, "backend": str}
"""

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

from agent import _extract_qasm, agent_chat
from runtime import run

_HERE = os.path.dirname(__file__)
_INDEX = os.path.join(_HERE, "index.html")
# originq's CPU simulator is little-endian and needs no bit-order handling, so it
# is a clean default for the "run it" button.
_DEFAULT_TARGET = "originq"


class Handler(BaseHTTPRequestHandler):
    def _reply(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            with open(_INDEX, "rb") as fh:
                self._reply(200, fh.read(), "text/html; charset=utf-8")
        else:
            self._reply(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._reply(400, {"error": "invalid JSON"})
            return

        try:
            if self.path == "/api/chat":
                reply = agent_chat(str(payload.get("prompt", "")))
                self._reply(200, {"reply": reply, "qasm": _extract_qasm(reply)})
            elif self.path == "/api/run":
                result = run(
                    str(payload.get("qasm", "")),
                    _DEFAULT_TARGET,
                    int(payload.get("shots", 1024)),
                )
                self._reply(200, {"counts": result["counts"], "backend": result["backend"]})
            else:
                self._reply(404, {"error": "not found"})
        except Exception as exc:  # noqa: BLE001 - surface a short message to the UI
            self._reply(500, {"error": str(exc).splitlines()[-1][:200]})

    def log_message(self, *args):  # keep the console quiet
        pass


def main():
    port = int(os.environ.get("PORT", "8000"))
    print(f"LoomQ web UI running at http://localhost:{port}  (Ctrl+C to stop)")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
