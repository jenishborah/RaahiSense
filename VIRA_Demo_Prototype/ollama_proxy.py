
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TOKEN = os.environ.get("VIRA_PROXY_TOKEN")
HOST = "127.0.0.1"
PORT = 8765
OLLAMA_URL = "http://127.0.0.1:11434"

if not TOKEN:
    raise RuntimeError("Set VIRA_PROXY_TOKEN before starting the proxy.")


class OllamaProxy(BaseHTTPRequestHandler):
    def send_json(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def authorized(self):
        supplied = self.headers.get("Authorization", "")
        return supplied == f"Bearer {TOKEN}"

    def forward(self, method, path):
        if path not in ("/api/tags", "/api/generate"):
            self.send_json(404, b'{"error":"Endpoint not allowed"}')
            return

        if not self.authorized():
            self.send_json(401, b'{"error":"Unauthorized"}')
            return

        body = None
        if method == "POST":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 1_000_000:
                    raise ValueError("Invalid request size")
                payload = json.loads(self.rfile.read(length))
                if path == "/api/generate":
                    if payload.get("model") != "llama3.2:3b":
                        self.send_json(400, b'{"error":"Model not allowed"}')
                        return
                    payload["stream"] = False
                body = json.dumps(payload).encode("utf-8")
            except (ValueError, json.JSONDecodeError):
                self.send_json(400, b'{"error":"Invalid JSON request"}')
                return

        request = Request(
            OLLAMA_URL + path,
            data=body,
            headers={"Content-Type": "application/json"},
            method=method,
        )

        try:
            with urlopen(request, timeout=180) as response:
                self.send_json(response.status, response.read())
        except HTTPError as error:
            self.send_json(error.code, error.read())
        except (URLError, TimeoutError, OSError):
            self.send_json(502, b'{"error":"Local Ollama is unavailable"}')

    def do_GET(self):
        self.forward("GET", self.path)

    def do_POST(self):
        self.forward("POST", self.path)

    def log_message(self, fmt, *args):
        # Avoid logging request headers or credentials.
        print(f"{self.client_address[0]} - {fmt % args}")


print(f"Authenticated Ollama proxy listening on http://{HOST}:{PORT}")
ThreadingHTTPServer((HOST, PORT), OllamaProxy).serve_forever()
