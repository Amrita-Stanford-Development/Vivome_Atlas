"""Implements `POST /api/project` exactly as published in
docs/service/projection-api.md, backed by the Stage 1-8 pipeline in
service/pipeline/.

Stdlib only (http.server + email, for multipart parsing without the
deprecated `cgi` module) — this is one small, well-defined endpoint, not a
reason to add a web framework dependency.

The reference bundle (encoder + reference embeddings/centroids/properties,
and for v3.1 its spec, read and validated once) loads when the server
starts and is cached once it loads. A load that fails is not cached: every
request tries again, so files fetched while the process runs are picked up
without a restart. Until then both endpoints answer with the reason: 503
for a missing or not-yet-fetched artifact, 500 for any other load error.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import statistics
import threading
from email import message_from_bytes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from service import config
from service.pipeline import alignment, gene_ids, pipeline, reference, validation

logger = logging.getLogger("vivome.projection_service")

_bundle: pipeline.ReferenceBundle | None = None
# ThreadingHTTPServer serves every request on its own thread; without this,
# a burst of concurrent first requests can each see _bundle is None and each
# call the expensive ReferenceBundle.load() (torch.load plus a full PCA fit)
# at once.
_bundle_lock = threading.Lock()
# How many projections may run at once (config.MAX_CONCURRENT_PROJECTIONS).
# A request that finds every slot taken is answered 503 at once, with a
# Retry-After, rather than queued behind a projection that may take minutes.
_projection_slots = threading.BoundedSemaphore(max(1, config.MAX_CONCURRENT_PROJECTIONS))
_DISCARD_CHUNK = 1024 * 1024


def _get_bundle() -> pipeline.ReferenceBundle:
    """The loaded bundle; raises whatever the load raised. Nothing is
    remembered from a failed load, so the next call checks the files again."""
    global _bundle
    if _bundle is not None:
        return _bundle
    with _bundle_lock:
        # Re-check inside the lock: another thread may have finished loading
        # while this one was waiting for it.
        if _bundle is None:
            # The identifier map every upload needs, first (it is quick): a
            # missing one is the service's fault, said here, not a 400 blaming
            # the visitor's file.
            gene_ids.load_gene_id_map()
            _bundle = pipeline.load_bundle(config.PIPELINE_VERSION)
            logger.info("Reference bundle loaded. model_version=%s", _bundle.model_version)
        return _bundle


def _bundle_or_error() -> tuple[pipeline.ReferenceBundle | None, int, str]:
    """(bundle, 200, "") or (None, status, reason): 503 while an artifact is
    missing, 500 for any other load error. Either way the client gets an
    answer with the reason, never a dropped connection."""
    try:
        return _get_bundle(), 200, ""
    except reference.PendingArtifactError as exc:
        return None, 503, _from_the_repository(str(exc))
    except Exception as exc:  # noqa: BLE001 — a broken artifact must still produce an HTTP answer
        logger.exception("could not load the reference bundle")
        return None, 500, _from_the_repository(f"the reference could not be loaded: {type(exc).__name__}: {exc}")


def _from_the_repository(reason: str) -> str:
    """A reason with its file paths written from the repository's root
    (service/model/...), not the server's own disk; the log keeps them whole."""
    root = config.SERVICE_ROOT.parent
    for prefix in (str(root), root.as_posix()):
        reason = reason.replace(prefix + "\\", "").replace(prefix + "/", "")
    return reason


def _parse_multipart(content_type: str, body: bytes) -> dict[str, bytes]:
    """Uses email.parser rather than the deprecated cgi module: wrap the
    body with a synthetic MIME header so the stdlib multipart parser can be
    reused directly."""
    header = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("ascii")
    message = message_from_bytes(header + body)
    if not message.is_multipart():  # no boundary: answered 400, not a dropped connection
        raise ValueError("the form has no parts (its multipart boundary is missing)")
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


VALUE_SCALE_CHOICES = ("auto", *alignment.READINGS)
ZEROS_CHOICES = ("auto", *alignment.ZEROS)


def _parse_value_scale_field(value: bytes | None, modality: str) -> str | None:
    """Optional value_scale form field: the upload's scale as the user
    states it ("linear" or "log"), or None for "auto", empty or absent,
    which leaves it to Stage 0's rule. Protein only: an RNA upload's scale is
    always read by the rule."""
    text = (value or b"").decode("utf-8").strip().lower()
    if text in ("", "auto"):
        return None
    if text not in alignment.READINGS:
        raise ValueError(f"value_scale must be one of {', '.join(VALUE_SCALE_CHOICES)}, got {text!r}")
    if modality != "prot":
        raise ValueError("value_scale can be stated only for a protein upload; an RNA upload's scale is read "
                         "by the service (send auto, or leave the field out)")
    return text


def _parse_zeros_field(value: bytes | None, stated_scale: str | None) -> str | None:
    """Optional zeros form field: what a 0 in the table means ("missing" or
    "measured"), or None for "auto", empty or absent. Only with value_scale
    log: read as raw intensities, every 0 is not detected."""
    text = (value or b"").decode("utf-8").strip().lower()
    if text in ("", "auto"):
        return None
    if text not in alignment.ZEROS:
        raise ValueError(f"zeros must be one of {', '.join(ZEROS_CHOICES)}, got {text!r}")
    if stated_scale != "log":
        raise ValueError("zeros can be stated only with value_scale log: read as raw intensities, every 0 is not "
                         "detected (and an RNA upload's scale is read by the service)")
    return text


def _decode_matrix(data: bytes) -> str:
    """The matrix file's text. UTF-8 (a byte order mark is left for the
    parser), UTF-16 with its byte order mark (Excel's "Unicode Text"), or
    else Windows-1252 (Excel's plain "CSV" on Windows: numbers and gene
    symbols are ASCII either way). An Excel workbook or another binary file
    is refused in words."""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        if len(data) % 2:  # cut off mid-character, perhaps mid-number: never read short
            raise alignment.UnreadableMatrix("the file ends in half a character, so it looks cut off: save it again and send the new file")
        return data.decode("utf-16", errors="replace")
    if data.startswith(b"PK\x03\x04"):
        raise alignment.UnreadableMatrix("the matrix is an Excel workbook (.xlsx), not text: save the sheet as CSV or "
                                         "tab-separated text and send that file")
    # Parquet starts and ends with "PAR1"; a text file may start with it (a cell's name).
    if (data.startswith(b"PAR1") and data.endswith(b"PAR1")) or b"\x00" in data[:4096]:
        raise alignment.UnreadableMatrix("the matrix is a binary file (Parquet, for example), not text: send it as CSV "
                                         "or tab-separated text")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


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
        """Lets the site's Atlas page read the response when it is
        served from an allowed origin (config.ALLOWED_ORIGINS); any other
        origin gets no CORS headers, so a browser keeps the response from it."""
        origin = self.headers.get("Origin")
        if origin and origin in config.ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def _send_json(self, status: int, payload: dict, headers: dict[str, str] | None = None) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _discard_body(self, length: int) -> None:
        """Reads and drops a body the service will not use, in small chunks,
        so the client is still sending when it gets the answer rather than
        finding the connection reset."""
        while length > 0:
            chunk = self.rfile.read(min(length, _DISCARD_CHUNK))
            if not chunk:
                break
            length -= len(chunk)

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

    def _from_the_site(self) -> bool:
        """With config.PROXY_SECRET set, only a request carrying it (one the
        website's /api door forwarded) is answered; a refused one gets 403."""
        if not config.PROXY_SECRET:
            return True
        given = self.headers.get(config.PROXY_SECRET_HEADER, "")
        if hmac.compare_digest(given.encode("utf-8"), config.PROXY_SECRET.encode("utf-8")):
            return True
        self.close_connection = True
        self._send_json(403, {
            "error": "this service answers only through its website",
            "reason": "Use the Atlas page's Your data tab, or run your own copy of the service "
                      "(service/README.md).",
        })
        return False

    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        """GET /api/status: whether the service can project, and with which
        model, so the site's Atlas page can say so before an upload.
        Loads the reference on first call, which also warms the service up."""
        if not self._from_the_site():
            return
        if self.path != "/api/status":
            self._send_json(404, {"error": f"no such endpoint: {self.path}"})
            return
        bundle, status, reason = _bundle_or_error()
        if bundle is None:
            self._send_json(status, {"status": "unavailable", "reason": reason})
            return
        self._send_json(200, {
            "status": "ready",
            "atlas_version": config.ATLAS_VERSION,
            "model_version": bundle.model_version,
            "pipeline_version": bundle.pipeline_version,
            "limits": {"max_cells": config.MAX_UPLOAD_CELLS,
                       "max_upload_mb": round(config.MAX_UPLOAD_BYTES / 2**20, 1),
                       "concurrent_projections": max(1, config.MAX_CONCURRENT_PROJECTIONS)},
            "value_scale": {"choices": list(VALUE_SCALE_CHOICES), "modalities": ["prot"], "zeros": list(ZEROS_CHOICES)},
        })

    def do_POST(self) -> None:  # noqa: N802 (stdlib naming)
        if not self._from_the_site():
            return
        if self.path != "/api/project":
            self._send_json(404, {"error": f"no such endpoint: {self.path}"})
            return

        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self._send_json(400, {"error": "Content-Type must be multipart/form-data"})
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            if length < 0:
                raise ValueError(length)
        except ValueError:
            self.close_connection = True
            self._send_json(400, {"error": "Content-Length must be a whole number of bytes"})
            return
        if length > config.MAX_UPLOAD_BYTES:
            self._discard_body(length)
            self._send_json(413, {
                "error": f"the upload is {length / 2**20:.1f} MB; this service accepts at most "
                         f"{config.MAX_UPLOAD_BYTES / 2**20:.0f} MB per request",
                "reason": "Split the cells at random into smaller files, so each is still a mix of cell types, "
                          "or run the service yourself with VIVOME_MAX_UPLOAD_MB raised.",
            })
            return
        body = self.rfile.read(length)

        try:
            fields = _parse_multipart(content_type, body)
            modality = fields["modality"].decode("utf-8")
            if modality not in ("rna", "prot"):
                self._send_json(400, {"error": f"modality must be 'rna' or 'prot', got {modality!r}"})
                return
            try:
                stated_scale = _parse_value_scale_field(fields.get("value_scale"), modality)
                stated_zeros = _parse_zeros_field(fields.get("zeros"), stated_scale)
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            matrix_text = _decode_matrix(fields["matrix"])
            # Restricted mode was retired (owner, 2026-10-21): every label is
            # chosen among all the reference's classes.
            if _parse_bool_field(fields.get("restrict_to_supported_classes")):
                self._send_json(400, {"error": "restrict_to_supported_classes is retired: every label is chosen among "
                                               "all the reference's classes; send the file without it"})
                return
            restrict = False
        except KeyError as exc:
            self._send_json(400, {"error": f"missing required field: {exc}"})
            return
        except alignment.UnreadableMatrix as exc:
            self._send_json(400, {"error": str(exc)})
            return
        except (UnicodeDecodeError, ValueError) as exc:
            self._send_json(400, {"error": f"malformed request: {exc}"})
            return

        bundle, status, reason = _bundle_or_error()
        if bundle is None:
            self._send_json(status, {
                "error": "projection service not yet available",
                "reason": reason,
                "see": "docs/service/download-checklist.md and service/model/README.md",
            })
            return

        # Parsing a large table takes several times its size in memory, so it
        # happens inside a projection slot too: one upload's work at a time.
        if not _projection_slots.acquire(blocking=False):
            self._send_json(503, {
                "error": "the service is busy with another upload",
                "reason": f"It projects {max(1, config.MAX_CONCURRENT_PROJECTIONS)} at a time. "
                          f"Try again in about {config.BUSY_RETRY_AFTER_SECONDS} seconds.",
            }, headers={"Retry-After": str(config.BUSY_RETRY_AFTER_SECONDS)})
            return
        try:
            try:
                raw = alignment.parse_matrix_csv(matrix_text)
                warnings = validation.validate(raw)
            except (validation.ValidationError, alignment.UnreadableMatrix) as exc:
                self._send_json(400, {"error": str(exc)})
                return
            except Exception:  # noqa: BLE001 — a malformed upload must not 500 silently
                logger.exception("could not parse the submitted matrix")
                self._send_json(400, {"error": "could not process the submitted matrix"})
                return

            if len(raw.cell_ids) > config.MAX_UPLOAD_CELLS:
                self._send_json(413, {
                    "error": f"the matrix has {len(raw.cell_ids):,} cells; this service projects at most "
                             f"{config.MAX_UPLOAD_CELLS:,} per upload",
                    "reason": "Split the cells at random into uploads of at most that many, so each is still a mix of "
                              "cell types, or run the service yourself with VIVOME_MAX_UPLOAD_CELLS raised.",
                })
                return

            try:
                result = pipeline.run_projection(bundle, raw, restrict_to_supported_classes=restrict, modality=modality,
                                                 stated_scale=stated_scale, stated_zeros=stated_zeros)
            except alignment.NotIntensities as exc:  # a linear reading stated for a log or centred table
                self._send_json(400, {"error": str(exc), "reason": "Choose Already log, or Automatic, for this file."})
                return
            except Exception:  # noqa: BLE001 — a malformed upload must not 500 silently
                logger.exception("projection failed")
                self._send_json(400, {"error": "could not process the submitted matrix"})
                return
        finally:
            _projection_slots.release()

        _log_upload(matrix_text, result)

        if warnings.low_cell_count:
            result.setdefault("warnings", []).append(
                f"fewer than {validation.MIN_CELLS_WARN} cells uploaded — "
                "per-upload statistics (smoothing, coverage) are less reliable at this size."
            )
        self._send_json(200, result)

    def log_message(self, format: str, *args) -> None:  # noqa: A002 (stdlib signature)
        logger.info("%s - %s", self.address_string(), format % args)


def main(host: str | None = None, port: int | None = None) -> None:
    """Serves on config.HOST and config.PORT (VIVOME_HOST, VIVOME_PORT) unless
    given others."""
    host = config.HOST if host is None else host
    port = config.PORT if port is None else port
    logging.basicConfig(level=logging.INFO)
    server = ThreadingHTTPServer((host, port), ProjectionHandler)
    # Load now, so the spec is read and checked at startup. A failure is
    # logged and retried on the first request.
    _, status, reason = _bundle_or_error()
    if status != 200:
        logger.warning("Reference bundle not loaded yet (%d): %s", status, reason)
    logger.info("Projection service listening on http://%s:%d/api/project (at most %d cells and %.0f MB per "
                "upload, %d projection(s) at once; origins %s)", host, port, config.MAX_UPLOAD_CELLS,
                config.MAX_UPLOAD_BYTES / 2**20, max(1, config.MAX_CONCURRENT_PROJECTIONS),
                ",".join(config.ALLOWED_ORIGINS))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
