import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from service import app
from service.pipeline import coordinates, pipeline, reference
from service.tests import fixtures


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


def _post_multipart(url: str, modality: bytes, matrix: bytes) -> tuple[int, dict]:
    boundary = "TESTBOUNDARY"
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="modality"\r\n\r\n'.encode()
        + modality
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

    def test_unknown_path_is_404(self):
        status, payload = _post_multipart(f"{self.base_url}/not/a/real/endpoint", b"rna", b"gene,c1\n")
        self.assertEqual(status, 404)

    def test_bad_modality_is_400(self):
        status, payload = _post_multipart(f"{self.base_url}/api/project", b"not_a_modality", b"gene,c1\nA1BG,1.0\n")
        self.assertEqual(status, 400)
        self.assertIn("modality", payload["error"])

    def test_missing_bundle_artifacts_answer_503_not_500(self):
        """Real reference_embedding.npy/centroids.npy exist now
        (service/model/README.md), so this no longer happens by ambient
        accident — force it deliberately. The guarantee this test protects
        (a genuinely missing artifact answers 503, never a 500 crash) still
        matters, e.g. for a bad VIVOME_REFERENCE_EMBEDDING override."""
        with patch(
            "service.pipeline.reference.load_reference_embedding",
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
        for expected in ("n_cells=25", "feature_coverage=", "value_scale=", "supported_classes=",
                         "abstention_rate=", "model_version=", "gene_map_version="):
            self.assertIn(expected, line)


def _load_encoder_only():
    from service.pipeline import encoder
    return encoder.load_encoder()


if __name__ == "__main__":
    unittest.main()
