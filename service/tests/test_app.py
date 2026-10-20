import http.client
import importlib
import json
import os
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import numpy as np

from service import app, config
from service.pipeline import coordinates, pipeline, reference
from service.tests import fixtures

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


class ParseMultipartTests(unittest.TestCase):
    def test_extracts_named_fields(self):
        boundary = "BOUNDARY"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="modality"\r\n\r\n'
            "rna\r\n"
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="matrix"; filename="m.csv"\r\n\r\n'
            "gene,c1\nA1BG,1.0\n\r\n"
            f"--{boundary}--\r\n"
        ).encode("utf-8")
        fields = app._parse_multipart(f"multipart/form-data; boundary={boundary}", body)
        self.assertEqual(fields["modality"], b"rna")
        self.assertEqual(fields["matrix"], b"gene,c1\nA1BG,1.0\n")


def _post_multipart(url: str, modality: bytes, matrix: bytes, extra: dict[str, bytes] | None = None) -> tuple[int, dict]:
    status, _, payload = _post_multipart_with_headers(url, modality, matrix, extra)
    return status, payload


def _post_multipart_with_headers(url: str, modality: bytes, matrix: bytes,
                                 extra: dict[str, bytes] | None = None) -> tuple[int, dict, dict]:
    boundary = "TESTBOUNDARY"
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="modality"\r\n\r\n'.encode()
        + modality
        + b"".join(f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'.encode() + value
                   for name, value in (extra or {}).items())
        + f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="matrix"; filename="m.csv"\r\n\r\n'.encode()
        + matrix
        + f"\r\n--{boundary}--\r\n".encode()
    )
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, dict(response.headers), json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), json.loads(exc.read())


class DecodeMatrixTests(unittest.TestCase):
    """The matrix file's bytes as text: the encodings spreadsheet programs
    write are read, and a file that is not text is refused in words."""

    def test_utf8_with_or_without_a_byte_order_mark(self):
        self.assertEqual(app._decode_matrix("gene,c\u00b51\n".encode("utf-8")), "gene,c\u00b51\n")
        self.assertTrue(app._decode_matrix("\ufeffgene,c1\n".encode("utf-8")).endswith("gene,c1\n"))

    def test_utf16_with_its_byte_order_mark_as_excel_writes_unicode_text(self):
        self.assertEqual(app._decode_matrix("gene\tc1\nA1BG\t1.5\n".encode("utf-16")), "gene\tc1\nA1BG\t1.5\n")

    def test_windows_1252_as_excel_writes_plain_csv(self):
        self.assertEqual(app._decode_matrix("gene,20 \u00b5m\nA1BG,1.5\n".encode("cp1252")), "gene,20 \u00b5m\nA1BG,1.5\n")

    def test_utf16_with_an_odd_last_byte_is_read_as_the_browser_reads_it(self):
        """The browser's decoder puts U+FFFD for a lone last byte; the service
        reads the file too, instead of refusing it before its slot."""
        data = b"\xff\xfe" + "gene,c1\nA1BG,1.5\n".encode("utf-16-le") + b"\x00"
        self.assertTrue(app._decode_matrix(data).startswith("gene,c1\nA1BG,1.5\n"))

    def test_a_workbook_or_a_binary_file_is_refused_in_words(self):
        with self.assertRaises(ValueError) as caught:
            app._decode_matrix(b"PK\x03\x04" + bytes(40))
        self.assertIn("Excel workbook", str(caught.exception))
        with self.assertRaises(ValueError) as caught:
            app._decode_matrix(b"PAR1" + bytes(40) + b"PAR1")
        self.assertIn("not text", str(caught.exception))
        # text that merely starts with "PAR1" (a cell's name) is text
        self.assertEqual(app._decode_matrix(b"PAR1_a,PAR1_b\nG0,1,2\n"), "PAR1_a,PAR1_b\nG0,1,2\n")


class ProjectionHandlerHttpTests(unittest.TestCase):
    """A real HTTP round trip against ThreadingHTTPServer, so "wired up
    end-to-end" means the actual socket path, not just direct function
    calls."""

    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app.ProjectionHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join()

    def setUp(self):
        app._bundle = None

    def _get(self, path, headers=None, method="GET"):
        request = urllib.request.Request(f"{self.base_url}{path}", method=method, headers=headers or {})
        try:
            with urllib.request.urlopen(request) as response:
                body = response.read()
                return response.status, dict(response.headers), json.loads(body) if body else None
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers), json.loads(exc.read())

    def test_status_says_ready_with_the_model_once_the_reference_loads(self):
        self._install_synthetic_bundle()
        status, _, payload = self._get("/api/status")
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["atlas_version"], config.ATLAS_VERSION)
        self.assertIn("model_version", payload)

    def test_status_answers_503_with_the_reason_when_an_artifact_is_missing(self):
        with patch("service.pipeline.pipeline.load_bundle",
                   side_effect=reference.PendingArtifactError("forced for this test")):
            status, _, payload = self._get("/api/status")
        self.assertEqual(status, 503)
        self.assertEqual(payload["status"], "unavailable")
        self.assertIn("forced for this test", payload["reason"])

    def test_an_allowed_origin_may_read_responses_and_others_may_not(self):
        self._install_synthetic_bundle()
        allowed = config.ALLOWED_ORIGINS[0]
        _, headers, _ = self._get("/api/status", {"Origin": allowed})
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), allowed)
        _, headers, _ = self._get("/api/status", {"Origin": "https://example.com"})
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_preflight_allows_the_site_including_a_private_network_request(self):
        allowed = config.ALLOWED_ORIGINS[0]
        status, headers, _ = self._get("/api/project", {
            "Origin": allowed, "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Private-Network": "true",
        }, method="OPTIONS")
        self.assertEqual(status, 204)
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), allowed)
        self.assertEqual(headers.get("Access-Control-Allow-Private-Network"), "true")
        self.assertIn("POST", headers.get("Access-Control-Allow-Methods", ""))

    def test_unknown_path_is_404(self):
        status, payload = _post_multipart(f"{self.base_url}/not/a/real/endpoint", b"rna", b"gene,c1\n")
        self.assertEqual(status, 404)

    def test_bad_modality_is_400(self):
        status, payload = _post_multipart(f"{self.base_url}/api/project", b"not_a_modality", b"gene,c1\nA1BG,1.0\n")
        self.assertEqual(status, 400)
        self.assertIn("modality", payload["error"])

    def test_missing_bundle_artifacts_answer_503_not_500(self):
        """The real artifacts exist (service/model/README.md), so force a
        missing one. The guarantee this test protects (a genuinely missing
        artifact answers 503, never a 500 crash) matters for a bad path
        override, or v3.1's checkpoints not yet fetched."""
        with patch(
            "service.pipeline.pipeline.load_bundle",
            side_effect=reference.PendingArtifactError("forced for this test"),
        ):
            status, payload = _post_multipart(f"{self.base_url}/api/project", b"rna", b"gene,c1\nA1BG,1.0\n")
        self.assertEqual(status, 503)
        self.assertIn("reason", payload)

    def test_a_load_error_answers_500_with_the_reason_on_both_endpoints(self):
        with patch("service.pipeline.pipeline.load_bundle", side_effect=OSError("disk unreadable")):
            status, _, payload = self._get("/api/status")
            self.assertEqual(status, 500)
            self.assertIn("disk unreadable", payload["reason"])
            status, payload = _post_multipart(f"{self.base_url}/api/project", b"rna", b"gene,c1\nA1BG,1.0\n")
            self.assertEqual(status, 500)
            self.assertIn("disk unreadable", payload["reason"])

    def test_a_missing_gene_identifier_map_is_the_service_s_fault_said_at_load(self):
        """Not a 400 blaming the visitor's file: the map every upload needs is
        checked when the reference loads."""
        from service.pipeline import gene_ids
        bundle = self._synthetic_bundle()
        with patch("service.pipeline.pipeline.load_bundle", return_value=bundle), \
                patch.object(gene_ids, "load_gene_id_map", side_effect=FileNotFoundError("gene_id_map_v1.tsv")):
            status, _, payload = self._get("/api/status")
        self.assertEqual(status, 500)
        self.assertIn("gene_id_map_v1.tsv", payload["reason"])

    def test_a_missing_artifact_is_checked_again_on_the_next_request(self):
        """Files fetched while the service runs are picked up without a restart."""
        bundle = self._synthetic_bundle()
        with patch("service.pipeline.pipeline.load_bundle",
                   side_effect=[reference.PendingArtifactError("not fetched yet"), bundle]) as load:
            first, _, payload = self._get("/api/status")
            second, _, _ = self._get("/api/status")
        self.assertEqual((first, second), (503, 200))
        self.assertIn("not fetched yet", payload["reason"])
        self.assertEqual(load.call_count, 2)

    def _install_synthetic_bundle(self):
        app._bundle = self._synthetic_bundle()
        return app._bundle.feature_genes

    def _synthetic_bundle(self):
        metadata = reference.load_reference_metadata()
        feature_genes = reference.load_feature_space_genes()
        embeddings, centroids = fixtures.synthetic_reference_embeddings(metadata)
        names, values = fixtures.synthetic_reference_properties(len(metadata.cell_ids))
        bundle = pipeline.ReferenceBundle(
            encoder_handle=_load_encoder_only(),
            feature_genes=feature_genes, metadata=metadata,
            reference_embeddings=embeddings, reference_centroids=centroids,
            reference_class_positions=metadata.class_positions_by_cell(),
            pca=coordinates.fit_pca_3d(embeddings), property_names=names, property_values=values,
            provenance=reference.load_provenance(),
        )
        return bundle

    def test_full_round_trip_with_a_synthetic_bundle_returns_200(self):
        feature_genes = self._install_synthetic_bundle()

        # 25 cells: above validation.MIN_CELLS_REFUSE (20) -- the minimum
        # cell count is Track B behavior, exercised on its own in
        # test_validation.py; this test's own concern is the 200 happy path.
        cell_ids = [f"c{i}" for i in range(25)]
        matrix_text = fixtures.synthetic_matrix_csv(feature_genes[:100], cell_ids)
        status, payload = _post_multipart(f"{self.base_url}/api/project", b"prot", matrix_text.encode())
        self.assertEqual(status, 200)
        self.assertEqual(payload["n_cells"], 25)
        self.assertEqual(len(payload["cells"]), 25)

    def test_a_successful_upload_emits_a_per_upload_log_line(self):
        feature_genes = self._install_synthetic_bundle()
        cell_ids = [f"c{i}" for i in range(25)]
        matrix_text = fixtures.synthetic_matrix_csv(feature_genes[:100], cell_ids)

        with self.assertLogs("vivome.projection_service", level="INFO") as captured:
            status, _ = _post_multipart(f"{self.base_url}/api/project", b"prot", matrix_text.encode())
        self.assertEqual(status, 200)

        upload_lines = [line for line in captured.output if "upload input_hash=" in line]
        self.assertEqual(len(upload_lines), 1)
        line = upload_lines[0]
        for expected in ("n_cells=25", "feature_coverage=", "value_scale=", "label_space=unrestricted",
                         "abstention_rate=", "model_version=", "gene_map_version="):
            self.assertIn(expected, line)

    def test_the_same_file_posted_twice_gives_identical_output(self):
        # 200 randomly drawn genes: an upload whose conformal sets depend on the
        # calibration slice. Checked to fail against the old unseeded code.
        feature_genes = self._install_synthetic_bundle()
        genes = list(np.random.default_rng(1).choice(feature_genes, size=200, replace=False))
        matrix = fixtures.synthetic_matrix_csv(genes, [f"c{i}" for i in range(80)]).encode()
        first = _post_multipart(f"{self.base_url}/api/project", b"prot", matrix)
        second = _post_multipart(f"{self.base_url}/api/project", b"prot", matrix)
        self.assertEqual(first[0], 200)
        self.assertEqual(first, second)

    def test_label_space_is_unrestricted_by_default_and_restricted_on_request(self):
        feature_genes = self._install_synthetic_bundle()
        matrix = fixtures.synthetic_matrix_csv(feature_genes[:100], [f"c{i}" for i in range(25)]).encode()
        url = f"{self.base_url}/api/project"

        status, default = _post_multipart(url, b"prot", matrix)
        self.assertEqual(status, 200)
        self.assertFalse(default["label_space"]["restricted_to_supported_classes"])
        self.assertEqual(len(default["label_space"]["candidate_classes"]), 22)

        status, restricted = _post_multipart(url, b"prot", matrix, {"restrict_to_supported_classes": b"true"})
        self.assertEqual(status, 200)
        self.assertTrue(restricted["label_space"]["restricted_to_supported_classes"])
        self.assertEqual(set(restricted["label_space"]["candidate_classes"]), set(config.CROSS_MODAL_SUPPORTED_CLASSES))
        for cell in restricted["cells"]:
            self.assertTrue(set(cell["label_set"]) <= set(config.CROSS_MODAL_SUPPORTED_CLASSES))

    def test_a_table_with_text_where_numbers_belong_is_400_naming_the_column(self):
        self._install_synthetic_bundle()
        status, payload = _post_multipart(f"{self.base_url}/api/project", b"prot",
                                          b"gene,c1,Description\nA1BG,1.0,a glycoprotein\n")
        self.assertEqual(status, 400)
        self.assertIn("'Description'", payload["error"])
        self.assertIn("MaxQuant proteinGroups.txt", payload["error"])

    def test_a_malformed_restriction_option_is_400(self):
        status, payload = _post_multipart(f"{self.base_url}/api/project", b"prot", b"gene,c1\nA1BG,1.0\n",
                                          {"restrict_to_supported_classes": b"sometimes"})
        self.assertEqual(status, 400)
        self.assertIn("restrict_to_supported_classes", payload["error"])

    def test_with_a_secret_set_only_requests_from_the_site_are_answered(self):
        """The hosted copy answers only through its website's /api door, which
        adds the secret; anything else gets 403, before any work is done."""
        feature_genes = self._install_synthetic_bundle()
        matrix = fixtures.synthetic_matrix_csv(feature_genes[:100], [f"c{i}" for i in range(25)]).encode()
        right = {config.PROXY_SECRET_HEADER: "s3cret"}
        with patch.object(config, "PROXY_SECRET", "s3cret"):
            for headers in ({}, {config.PROXY_SECRET_HEADER: "wrong"}, {config.PROXY_SECRET_HEADER: ""}):
                status, _, payload = self._get("/api/status", headers=headers)
                self.assertEqual(status, 403, headers)
                self.assertIn("only through its website", payload["error"])
            status, _, payload = self._get("/api/status", headers=right)
            self.assertEqual((status, payload["status"]), (200, "ready"))
            status, payload = _post_multipart(f"{self.base_url}/api/project", b"prot", matrix)
            self.assertEqual(status, 403)
            status, _, payload = self._get("/api/nowhere", headers={})
            self.assertEqual(status, 403, "not even which paths exist")
        # Unset (a copy run at home): every request is answered.
        status, _, payload = self._get("/api/status")
        self.assertEqual(status, 200)

    def test_status_reports_the_upload_limits(self):
        self._install_synthetic_bundle()
        status, _, payload = self._get("/api/status")
        self.assertEqual(status, 200)
        self.assertEqual(payload["limits"]["max_cells"], config.MAX_UPLOAD_CELLS)
        self.assertEqual(payload["limits"]["max_upload_mb"], round(config.MAX_UPLOAD_BYTES / 2**20, 1))
        self.assertGreaterEqual(payload["limits"]["concurrent_projections"], 1)

    def test_an_upload_over_the_byte_cap_is_413_with_the_reason(self):
        """The body is read and dropped before the answer, so the client gets
        the 413 rather than a reset connection."""
        feature_genes = self._install_synthetic_bundle()
        matrix = fixtures.synthetic_matrix_csv(feature_genes[:100], [f"c{i}" for i in range(25)]).encode()
        with patch.object(config, "MAX_UPLOAD_BYTES", 1024):
            status, payload = _post_multipart(f"{self.base_url}/api/project", b"prot", matrix)
        self.assertEqual(status, 413)
        self.assertIn("at most", payload["error"])
        self.assertIn("VIVOME_MAX_UPLOAD_MB", payload["reason"])

    def test_an_upload_over_the_cell_cap_is_413_with_the_reason(self):
        feature_genes = self._install_synthetic_bundle()
        matrix = fixtures.synthetic_matrix_csv(feature_genes[:100], [f"c{i}" for i in range(25)]).encode()
        with patch.object(config, "MAX_UPLOAD_CELLS", 24):
            status, payload = _post_multipart(f"{self.base_url}/api/project", b"prot", matrix)
        self.assertEqual(status, 413)
        self.assertIn("25 cells", payload["error"])
        self.assertIn("at most 24", payload["error"])

    def test_a_request_finding_every_slot_taken_is_503_with_retry_after(self):
        feature_genes = self._install_synthetic_bundle()
        matrix = fixtures.synthetic_matrix_csv(feature_genes[:100], [f"c{i}" for i in range(25)]).encode()
        url = f"{self.base_url}/api/project"
        with patch.object(app, "_projection_slots", threading.BoundedSemaphore(1)) as slots:
            slots.acquire()  # another upload is projecting
            status, headers, payload = _post_multipart_with_headers(url, b"prot", matrix)
            self.assertEqual(status, 503)
            self.assertEqual(headers.get("Retry-After"), str(config.BUSY_RETRY_AFTER_SECONDS))
            self.assertIn("busy", payload["error"])
            slots.release()  # that upload is done
            status, _, _ = _post_multipart_with_headers(url, b"prot", matrix)
            self.assertEqual(status, 200)

    def test_a_busy_service_answers_before_parsing_the_matrix(self):
        """Parsing a large table takes several times its size in memory, so it
        happens only inside a projection slot, one upload at a time."""
        feature_genes = self._install_synthetic_bundle()
        matrix = fixtures.synthetic_matrix_csv(feature_genes[:100], [f"c{i}" for i in range(25)]).encode()
        with patch.object(app, "_projection_slots", threading.BoundedSemaphore(1)) as slots, \
                patch.object(app.alignment, "parse_matrix_csv", wraps=app.alignment.parse_matrix_csv) as parse:
            slots.acquire()
            status, _ = _post_multipart(f"{self.base_url}/api/project", b"prot", matrix)
            slots.release()
        self.assertEqual(status, 503)
        parse.assert_not_called()

    def test_an_excel_workbook_is_400_saying_what_to_send(self):
        self._install_synthetic_bundle()
        status, payload = _post_multipart(f"{self.base_url}/api/project", b"prot", b"PK\x03\x04" + bytes(64))
        self.assertEqual(status, 400)
        self.assertIn("Excel workbook", payload["error"])

    def test_a_failed_projection_gives_its_slot_back(self):
        feature_genes = self._install_synthetic_bundle()
        matrix = fixtures.synthetic_matrix_csv(feature_genes[:100], [f"c{i}" for i in range(25)]).encode()
        with patch.object(app, "_projection_slots", threading.BoundedSemaphore(1)) as slots, \
                patch("service.pipeline.pipeline.run_projection", side_effect=RuntimeError("forced")):
            status, _ = _post_multipart(f"{self.base_url}/api/project", b"prot", matrix)
            self.assertEqual(status, 400)
            self.assertTrue(slots.acquire(blocking=False))
            slots.release()

    def test_a_malformed_content_length_is_400(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=30)
        try:
            connection.putrequest("POST", "/api/project")
            connection.putheader("Content-Type", "multipart/form-data; boundary=X")
            connection.putheader("Content-Length", "many")
            connection.endheaders()
            response = connection.getresponse()
            self.assertEqual(response.status, 400)
            self.assertIn("Content-Length", json.loads(response.read())["error"])
        finally:
            connection.close()

    def test_real_dia_nn_pbmc240_upload_runs_end_to_end(self):
        """Track B follow-up: the actual PBMC_240cells_proteins.tsv DIA-NN
        report (service/examples/pbmc240_proteins_raw.tsv -- the same file
        service/examples/pbmc240_provenance.json describes), tab-separated
        with real DIA-NN annotation columns, run through the real HTTP
        endpoint end to end -- not a synthetic fixture, and not the pipeline
        stages called directly (see test_e2e_real_export.py for that
        variant)."""
        self._install_synthetic_bundle()
        matrix_bytes = (EXAMPLES / "pbmc240_proteins_raw.tsv").read_bytes()

        status, payload = _post_multipart(f"{self.base_url}/api/project", b"prot", matrix_bytes)

        self.assertEqual(status, 200)
        self.assertEqual(payload["n_cells"], 238)

        cell_ids = [cell["cell_id"] for cell in payload["cells"]]
        self.assertTrue(all("\\" not in cid and not cid.lower().endswith(".raw") for cid in cell_ids))

        observed_genes = sorted(cell["observed_genes"] for cell in payload["cells"])
        n_pass_floor = sum(1 for g in observed_genes if g >= config.MIN_OBSERVED_GENES)
        print(
            f"\n[integration] real PBMC240 DIA-NN upload: {n_pass_floor}/{len(observed_genes)} "
            f"cells pass the {config.MIN_OBSERVED_GENES}-gene floor; observed_genes "
            f"min={observed_genes[0]} median={observed_genes[len(observed_genes) // 2]} "
            f"max={observed_genes[-1]}"
        )
        self.assertGreater(observed_genes[-1], 0)


def _load_encoder_only():
    from service.pipeline import encoder
    return encoder.load_encoder()


class HostingSettingsTests(unittest.TestCase):
    """What a deployment sets through the environment (deploy/huggingface/)."""

    def tearDown(self):
        importlib.reload(config)  # back to this process's own environment

    def test_the_environment_sets_where_to_listen_and_the_upload_limits(self):
        with patch.dict(os.environ, {"VIVOME_HOST": "0.0.0.0", "VIVOME_PORT": "7860",
                                     "VIVOME_MAX_UPLOAD_CELLS": "50", "VIVOME_MAX_UPLOAD_MB": "1.5",
                                     "VIVOME_MAX_CONCURRENT_PROJECTIONS": "2",
                                     "VIVOME_ALLOWED_ORIGINS": "https://vivome-atlas.pages.dev"}):
            importlib.reload(config)
            self.assertEqual((config.HOST, config.PORT), ("0.0.0.0", 7860))
            self.assertEqual(config.MAX_UPLOAD_CELLS, 50)
            self.assertEqual(config.MAX_UPLOAD_BYTES, int(1.5 * 1024 * 1024))
            self.assertEqual(config.MAX_CONCURRENT_PROJECTIONS, 2)
            self.assertEqual(config.ALLOWED_ORIGINS, ("https://vivome-atlas.pages.dev",))
            self.assertIsNone(config.PROXY_SECRET, "no secret unless one is set")
        with patch.dict(os.environ, {"VIVOME_PROXY_SECRET": "s3cret"}):
            importlib.reload(config)
            self.assertEqual(config.PROXY_SECRET, "s3cret")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("VIVOME_MAX_UPLOAD_MB", None)
            importlib.reload(config)
            self.assertEqual(config.MAX_UPLOAD_BYTES, 100 * 1024 * 1024, "100 MB: what the website's host takes in one request")

    def test_without_settings_the_service_listens_on_this_machine_only(self):
        unset = ("VIVOME_HOST", "VIVOME_PORT")
        with patch.dict(os.environ, {k: v for k, v in os.environ.items() if k not in unset}, clear=True):
            importlib.reload(config)
            self.assertEqual((config.HOST, config.PORT), ("127.0.0.1", 8001))

    def test_main_listens_where_the_settings_say(self):
        bound = []

        class FakeServer:
            def __init__(self, address, handler):
                bound.append(address)

            def serve_forever(self):
                raise KeyboardInterrupt

            def shutdown(self):
                pass

        with patch.object(config, "HOST", "0.0.0.0"), patch.object(config, "PORT", 7860), \
                patch.object(app, "ThreadingHTTPServer", FakeServer), \
                patch.object(app.logging, "basicConfig"), \
                patch.object(app, "_bundle_or_error", return_value=(None, 200, "")):
            app.main()
        self.assertEqual(bound, [("0.0.0.0", 7860)])


if __name__ == "__main__":
    unittest.main()
