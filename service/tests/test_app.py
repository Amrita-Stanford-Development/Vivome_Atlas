import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

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
        """No real reference_embedding.npy/centroids.npy exist yet, so a
        real server hit today must fail honestly, not crash."""
        status, payload = _post_multipart(f"{self.base_url}/api/project", b"rna", b"gene,c1\nA1BG,1.0\n")
        self.assertEqual(status, 503)
        self.assertIn("reason", payload)

    def test_full_round_trip_with_a_synthetic_bundle_returns_200(self):
        metadata = reference.load_reference_metadata()
        feature_genes = reference.load_feature_space_genes()
        embeddings, centroids = fixtures.synthetic_reference_embeddings(metadata)
        names, values = fixtures.synthetic_reference_properties(len(metadata.cell_ids))
        bundle = pipeline.ReferenceBundle(
            encoder_handle=_load_encoder_only(),
            feature_genes=feature_genes, metadata=metadata,
            reference_embeddings=embeddings, reference_centroids=centroids,
            pca=coordinates.fit_pca_3d(embeddings), property_names=names, property_values=values,
        )
        app._bundle = bundle
        app._bundle_error = None

        matrix_text = fixtures.synthetic_matrix_csv(feature_genes[:100], ["c1", "c2"])
        status, payload = _post_multipart(f"{self.base_url}/api/project", b"prot", matrix_text.encode())
        self.assertEqual(status, 200)
        self.assertEqual(payload["n_cells"], 2)
        self.assertEqual(len(payload["cells"]), 2)


def _load_encoder_only():
    from service.pipeline import encoder
    return encoder.load_encoder()


if __name__ == "__main__":
    unittest.main()
