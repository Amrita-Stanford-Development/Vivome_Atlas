import json
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
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


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
        app._bundle_error = None

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

    def _install_synthetic_bundle(self):
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
        app._bundle = bundle
        app._bundle_error = None
        return feature_genes

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

    def test_a_malformed_restriction_option_is_400(self):
        status, payload = _post_multipart(f"{self.base_url}/api/project", b"prot", b"gene,c1\nA1BG,1.0\n",
                                          {"restrict_to_supported_classes": b"sometimes"})
        self.assertEqual(status, 400)
        self.assertIn("restrict_to_supported_classes", payload["error"])

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


if __name__ == "__main__":
    unittest.main()
