"""deploy/huggingface/rehearse.py: the hosted image's settings, read from its
Dockerfile, for a local rehearsal of a deploy."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("rehearse", REPO / "deploy" / "huggingface" / "rehearse.py")
rehearse = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rehearse)


class HostedEnvTests(unittest.TestCase):
    def test_the_real_dockerfile_s_settings(self):
        env = rehearse.hosted_env()
        self.assertEqual(env["VIVOME_PIPELINE_VERSION"], "v4.1")
        self.assertEqual(env["VIVOME_MAX_UPLOAD_MB"], "31")
        self.assertEqual(env["VIVOME_MAX_UPLOAD_CELLS"], "2000")
        self.assertEqual(env["OMP_NUM_THREADS"], "2")
        self.assertEqual(env["VIVOME_ALLOWED_ORIGINS"], "https://vivome-atlas.pages.dev")

    def test_continued_lines_and_several_env_blocks_are_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Dockerfile"
            path.write_text("FROM python:3.11-slim\n# a comment, ENV A=no\nENV A=1 \\\n    B=two \\\n    C=x=y\n"
                            "RUN echo D=4\nENV D=5\n", encoding="utf-8")
            self.assertEqual(rehearse.hosted_env(path), {"A": "1", "B": "two", "C": "x=y", "D": "5"})

    def test_the_rehearsal_listens_on_this_machine_only_and_without_the_site_s_secret(self):
        env = rehearse.rehearsal_env(8765, {"VIVOME_PROXY_SECRET": "s", "PATH": "p"})
        self.assertEqual(env["VIVOME_HOST"], "127.0.0.1")
        self.assertEqual(env["VIVOME_PORT"], "8765")
        self.assertNotIn("VIVOME_PROXY_SECRET", env)
        self.assertEqual(env["VIVOME_MAX_UPLOAD_MB"], "31")
        self.assertEqual(env["PATH"], "p")


if __name__ == "__main__":
    unittest.main()
