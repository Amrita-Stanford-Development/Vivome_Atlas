"""Implements `POST /api/project` exactly as published in
docs/projection-service.md, backed by the Stage 1-8 pipeline in
service/pipeline/.

Stdlib only (http.server + email, for multipart parsing without the
deprecated `cgi` module) — this is one small, well-defined endpoint, not a
reason to add a web framework dependency.

The reference bundle (encoder + reference embeddings/centroids/properties)
loads once, lazily, on first request, and is cached. If it is missing a
pending artifact (see Download_Checklist.md, "Still waiting on"),
`/api/project` answers 503 with which artifact is blocking it, instead of
crashing the whole process — the server is legitimately "up" (dev
placeholder in-progress work can still hit other diagnostics) even before
the production reference lands.
"""
from __future__ import annotations

import json
import logging
from email import message_from_bytes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from service.pipeline import alignment, pipeline, reference

logger = logging.getLogger("vivome.projection_service")

_bundle: pipeline.ReferenceBundle | None = None
_bundle_error: str | None = None


def _get_bundle() -> pipeline.ReferenceBundle:
    global _bundle, _bundle_error
    if _bundle is not None:
        return _bundle
    if _bundle_error is not None:
        raise reference.PendingArtifactError(_bundle_error)
    try:
        _bundle = pipeline.ReferenceBundle.load()
        logger.info("Reference bundle loaded. model_version=%s", _bundle.model_version)
        return _bundle
    except reference.PendingArtifactError as exc:
        _bundle_error = str(exc)
        raise


def _parse_multipart(content_type: str, body: bytes) -> dict[str, bytes]:
    """Uses email.parser rather than the deprecated cgi module: wrap the
    body with a synthetic MIME header so the stdlib multipart parser can be
    reused directly."""
    header = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("ascii")
    message = message_from_bytes(header + body)
    fields: dict[str, bytes] = {}
    for part in message.get_payload():
        name = part.get_param("name", header="content-disposition")
        if name is None:
            continue
        payload = part.get_payload(decode=True)
        fields[name] = payload if payload is not None else b""
    return fields


class ProjectionHandler(BaseHTTPRequestHandler):
    server_version = "VivOMEProjectionService/0.1"

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802 (stdlib naming)
        if self.path != "/api/project":
            self._send_json(404, {"error": f"no such endpoint: {self.path}"})
            return

        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self._send_json(400, {"error": "Content-Type must be multipart/form-data"})
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        try:
            fields = _parse_multipart(content_type, body)
            modality = fields["modality"].decode("utf-8")
            if modality not in ("rna", "prot"):
                self._send_json(400, {"error": f"modality must be 'rna' or 'prot', got {modality!r}"})
                return
            matrix_text = fields["matrix"].decode("utf-8")
        except KeyError as exc:
            self._send_json(400, {"error": f"missing required field: {exc}"})
            return
        except (UnicodeDecodeError, ValueError) as exc:
            self._send_json(400, {"error": f"malformed request: {exc}"})
            return

        try:
            bundle = _get_bundle()
        except reference.PendingArtifactError as exc:
            self._send_json(503, {
                "error": "projection service not yet available",
                "reason": str(exc),
                "see": "Download_Checklist.md, 'Still waiting on', and service/model/README.md",
            })
            return

        try:
            raw = alignment.parse_matrix_csv(matrix_text)
            result = pipeline.run_projection(bundle, raw)
        except Exception:  # noqa: BLE001 — a malformed upload must not 500 silently
            logger.exception("projection failed")
            self._send_json(400, {"error": "could not process the submitted matrix"})
            return

        self._send_json(200, result)

    def log_message(self, format: str, *args) -> None:  # noqa: A002 (stdlib signature)
        logger.info("%s - %s", self.address_string(), format % args)


def main(host: str = "127.0.0.1", port: int = 8001) -> None:
    logging.basicConfig(level=logging.INFO)
    server = ThreadingHTTPServer((host, port), ProjectionHandler)
    logger.info("Projection service listening on http://%s:%d/api/project", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
