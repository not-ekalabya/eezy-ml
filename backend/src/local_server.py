"""Small HTTP adapter for running the Lambda handler in a local container."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import argparse
import json
from urllib.parse import parse_qs, urlparse

from app import handler


class LambdaHandlerAdapter(BaseHTTPRequestHandler):
    server_version = "EezyMLLocal/1.0"

    def do_OPTIONS(self):
        self._send_response(
            {
                "statusCode": 204,
                "headers": {
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type,Authorization",
                },
                "body": "",
            }
        )

    def do_GET(self):
        self._handle()

    def do_POST(self):
        self._handle()

    def _handle(self):
        parsed = urlparse(self.path)
        content_length = int(self.headers.get("Content-Length") or "0")
        raw_body = self.rfile.read(content_length).decode("utf-8") if content_length else ""
        query = parse_qs(parsed.query, keep_blank_values=True)

        event = {
            "path": parsed.path,
            "httpMethod": self.command,
            "headers": dict(self.headers.items()),
            "queryStringParameters": {key: values[-1] for key, values in query.items()},
            "body": raw_body,
            "isBase64Encoded": False,
        }

        try:
            response = handler(event, None)
        except Exception as exc:
            response = {
                "statusCode": 500,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": str(exc)}),
            }

        self._send_response(response)

    def _send_response(self, response):
        status = int(response.get("statusCode") or 200)
        headers = response.get("headers") or {}
        body = response.get("body") or ""
        if not isinstance(body, bytes):
            body = body.encode("utf-8")

        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, str(value))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description="Run the eezy-ml backend locally.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3000)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), LambdaHandlerAdapter)
    print(f"Backend listening on http://{args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
