"""Thin HTTP adapter over ``server.routes.Api`` (stdlib http.server).

Single-threaded dev server, same shape as V1's ``serve.py``: serves the static
dashboard from ``web/`` and dispatches ``/api/*`` to the handler methods. All
frontend calls are same-origin relative paths, so no CORS/base-URL config.
"""

from __future__ import annotations

import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from marketing_engine.config.settings import Settings
from marketing_engine.harness.engine import MarketingEngine
from marketing_engine.server.routes import Api


def default_web_dir() -> Path:
    """Locate the bundled ``web/`` dashboard dir (repo root in editable installs)."""

    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "web"
        if (candidate / "dashboard.html").is_file():
            return candidate
    return here.parents[3] / "web"


def _single(params: dict[str, list[str]]) -> dict:
    return {k: v[0] for k, v in params.items()}


def make_handler(api: Api, web_dir: Path):
    class Handler(BaseHTTPRequestHandler):
        server_version = "MarketingEngine/0.1"

        def log_message(self, *args):  # quieter logs
            pass

        # -- helpers ------------------------------------------------------
        def _send_json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_file(self, path: Path) -> None:
            if not path.is_file():
                self._send_json(404, {"error": "not found"})
                return
            ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
            data = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _read_body(self) -> dict:
            length = int(self.headers.get("Content-Length", 0) or 0)
            if not length:
                return {}
            raw = self.rfile.read(length)
            try:
                return json.loads(raw or b"{}")
            except json.JSONDecodeError:
                return {}

        # -- routing ------------------------------------------------------
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path
            params = _single(parse_qs(parsed.query))

            if path in ("/", "/index.html", "/dashboard.html"):
                self._send_file(web_dir / "dashboard.html")
                return

            routes = {
                "/api/brands": api.list_brands,
                "/api/platforms": api.platforms,
                "/api/lab/bundle-pack": lambda: api.bundle_pack(params),
                "/api/kb/list": lambda: api.kb_list(params),
                "/api/lab/session": lambda: api.session_get(params),
                "/api/lab/anthropic/status": api.anthropic_status,
                "/api/lab/bridge/status": api.bridge_status,
                "/api/engine/status": api.engine_status,
            }
            if path in routes:
                status, payload = routes[path]()
                self._send_json(status, payload)
                return
            if path.startswith("/api/"):
                status, payload = api.not_implemented(path)
                self._send_json(status, payload)
                return

            # static asset under web/
            rel = path.lstrip("/")
            target = (web_dir / rel).resolve()
            if web_dir in target.parents or target == web_dir:
                self._send_file(target)
            else:
                self._send_json(404, {"error": "not found"})

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            body = self._read_body()
            routes = {
                "/api/lab/generate": lambda: api.generate(body),
                "/api/lab/commit-edits": lambda: api.commit_edits(body),
                "/api/lab/save-draft": lambda: api.commit_edits(body),
                "/api/kb/upload": lambda: api.kb_upload(body),
                "/api/lab/session": lambda: api.session_post(body),
            }
            if path in routes:
                status, payload = routes[path]()
                self._send_json(status, payload)
                return
            status, payload = api.not_implemented(path)
            self._send_json(status, payload)

    return Handler


def serve(
    settings: Settings,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    web_dir: Path | None = None,
    llm=None,
) -> None:
    engine = MarketingEngine(settings, llm=llm)
    api = Api(engine)
    web = web_dir or default_web_dir()
    handler = make_handler(api, web)
    httpd = ThreadingHTTPServer((host, port), handler)
    print(f"Marketing Engine dashboard → http://{host}:{port}/  (vault: {settings.vault_root})")
    print(f"Serving dashboard from {web}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        httpd.shutdown()
