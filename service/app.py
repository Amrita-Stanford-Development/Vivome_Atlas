"""Implements `POST /api/project` exactly as published in
docs/service/projection-api.md, backed by the Stage 1-8 pipeline in
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
the production reference lands. A failed load is cached too, so dropping
the missing files in while the process is running does not self-heal —
restart the process to pick them up.
"""
from __future__ import annotations

import hashlib
import json
import logging
import statistics
import threading
from email import message_from_bytes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from service import config
from service.pipeline import alignment, pipeline, reference, validation

logger = logging.getLogger("vivome.projection_service")

_bundle: pipeline.ReferenceBundle | None = None
_bundle_error: str | None = None
# ThreadingHTTPServer serves every request on its own thread; without this,
# a burst of concurrent first requests can each see _bundle is None and each
# call the expensive ReferenceBundle.load() (torch.load plus a full PCA fit)
# at once.
_bundle_lock = threading.Lock()


def _get_bundle() -> pipeline.ReferenceBundle:
    global _bundle, _bundle_error
    if _bundle is not None:
        return _bundle
    if _bundle_error is not None:
        raise reference.PendingArtifactError(_bundle_error)
    with _bundle_lock:
        # Re-check inside the lock: another thread may have finished
        # loading (or failing) while this one was waiting for it.
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


def _parse_bool_field(value: bytes | None) -> bool:
    """Optional true/false form field; absent or empty means false."""
    text = (value or b"").decode("utf-8").strip().lower()
    if text in ("", "false", "0", "no"):
        return False
    if text in ("true", "1", "yes"):
        return True
    raise ValueError(f"restrict_to_supported_classes must be true or false, got {text!r}")


def _log_upload(matrix_text: str, result: dict) -> None:
    """Per-upload audit line (Track B) — enough to debug a bad projection or
    watch for drift (coverage collapsing, abstention rate climbing) without
    storing any cell-level data. `input_hash` lets the same upload be
    correlated across log lines without keeping the matrix itself."""
    reason_counts: dict[str, int] = {}
    for cell in result["cells"]:
        if cell["abstained"]:
            reason_counts[cell["abstain_reason"]] = reason_counts.get(cell["abstain_reason"], 0) + 1
    n_cells = result["n_cells"]
    n_abstained = sum(reason_counts.values())
    n_features_total = result["n_features_matched"] + result["n_features_unmatched"]

    logger.info(
        "upload input_hash=%s n_cells=%d feature_coverage=%.4f observed_genes_median=%s "
        "value_scale=%s label_space=%s abstention_rate=%.4f abstain_reasons=%s "
        "model_version=%s gene_map_version=%s",
        hashlib.sha256(matrix_text.encode("utf-8")).hexdigest()[:16],
        n_cells,
        result["n_features_matched"] / n_features_total if n_features_total else 0.0,
        statistics.median(cell["observed_genes"] for cell in result["cells"]) if result["cells"] else None,
        result["value_scale"],
        ("restricted:" + ",".join(result["label_space"]["candidate_classes"])
         if result["label_space"]["restricted_to_supported_classes"] else "unrestricted"),
        n_abstained / n_cells if n_cells else 0.0,
        reason_counts,
        result["model_version"],
        config.GENE_ID_MAP_PATH.stem,
    )


class ProjectionHandler(BaseHTTPRequestHandler):
    server_version = "VivOMEProjectionService/0.1"

    def _send_cors_headers(self) -> None:
        """Lets the site's projection page read the response when it is
        served from an allowed origin (config.ALLOWED_ORIGINS); any other
        origin gets no CORS headers, so a browser keeps the response from it."""
        origin = self.headers.get("Origin")
        if origin and origin in config.ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802 (stdlib naming)
        """CORS preflight. A plain FormData POST needs none, but a browser
        may still send one, for instance Chrome's check before a public
        page reaches a service on this machine (Private Network Access)."""
        self.send_response(204)
        self._send_cors_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        if self.headers.get("Access-Control-Request-Private-Network") == "true" \
                and self.headers.get("Origin") in config.ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        """GET /api/status: whether the service can project, and with which
        model, so the site's projection page can say so before an upload.
        Loads the reference on first call, which also warms the service up."""
        if self.path != "/api/status":
            self._send_json(404, {"error": f"no such endpoint: {self.path}"})
            return
        try:
            bundle = _get_bundle()
        except reference.PendingArtifactError as exc:
            self._send_json(503, {"status": "unavailable", "reason": str(exc)})
            return
        self._send_json(200, {
            "status": "ready",
            "atlas_version": config.ATLAS_VERSION,
            "model_version": bundle.model_version,
        })

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
            restrict = _parse_bool_field(fields.get("restrict_to_supported_classes"))
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
            warnings = validation.validate(raw)
        except validation.ValidationError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        except Exception:  # noqa: BLE001 — a malformed upload must not 500 silently
            logger.exception("could not parse the submitted matrix")
            self._send_json(400, {"error": "could not process the submitted matrix"})
            return

        try:
            result = pipeline.run_projection(bundle, raw, restrict_to_supported_classes=restrict)
        except Exception:  # noqa: BLE001 — a malformed upload must not 500 silently
            logger.exception("projection failed")
            self._send_json(400, {"error": "could not process the submitted matrix"})
            return

        _log_upload(matrix_text, result)

        if warnings.low_cell_count:
            result.setdefault("warnings", []).append(
                f"fewer than {validation.MIN_CELLS_WARN} cells uploaded — "
                "per-upload statistics (smoothing, coverage) are less reliable at this size."
            )
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
