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


class BuildSpaceHelpTests(unittest.TestCase):
    """build_space.py --help says what it does and builds nothing (it used to
    replace the staged Space)."""

    def test_help_builds_nothing(self):
        from unittest import mock
        spec = importlib.util.spec_from_file_location("build_space", REPO / "deploy" / "huggingface" / "build_space.py")
        build_space = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(build_space)
        with mock.patch.object(build_space, "runtime_files", side_effect=AssertionError("the build started")), \
                self.assertRaises(SystemExit) as caught:
            build_space.main(["--help"])
        self.assertEqual(caught.exception.code, 0)


class BuildSpaceFilesTests(unittest.TestCase):
    """Stage 0 reads a protein table with the raw-or-log package (B5), so the
    staged service carries the package and its shipped calibration."""

    def test_the_space_carries_the_raw_or_log_package(self):
        spec = importlib.util.spec_from_file_location("build_space", REPO / "deploy" / "huggingface" / "build_space.py")
        build_space = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(build_space)
        files = {p.relative_to(REPO).as_posix() for p in build_space.package_files()}
        for name in ("valuescale/__init__.py", "valuescale/method.py", "valuescale/calibration/protein-v1.json",
                     "service/pipeline/alignment.py"):
            self.assertIn(name, files)
        self.assertFalse([f for f in files if "/tests/" in f or "/corpus/" in f or "/bank/" in f], "no tests or data")
        dockerfile = (REPO / "deploy" / "huggingface" / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("COPY --chown=user valuescale ./valuescale", dockerfile)


def _build_space():
    spec = importlib.util.spec_from_file_location("build_space", REPO / "deploy" / "huggingface" / "build_space.py")
    build_space = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build_space)
    return build_space


class BuildSpaceChecksTests(unittest.TestCase):
    """B6 (research/value-scale-plan.md): the manifest's record of uncommitted
    changes covers valuescale/, and the staged packages import on their own."""

    def test_the_uncommitted_changes_check_covers_the_raw_or_log_package(self):
        from unittest import mock
        build_space = _build_space()
        with mock.patch.object(build_space, "git", return_value="") as git:
            self.assertFalse(build_space.uncommitted_changes())
        args = git.call_args.args
        self.assertEqual(args[:3], ("status", "--porcelain", "--"))
        self.assertEqual(set(args[3:]), {"service", "valuescale", "deploy"})
        with mock.patch.object(build_space, "git", return_value=" M valuescale/method.py"):
            self.assertTrue(build_space.uncommitted_changes())

    def _staged(self, tmp, leave_out=()):
        import shutil
        build_space = _build_space()
        for source in build_space.package_files():
            rel = source.relative_to(REPO).as_posix()
            if rel not in leave_out:
                (Path(tmp) / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, Path(tmp) / rel)
        return build_space

    def test_the_import_check_passes_on_the_staged_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            build_space = self._staged(tmp)
            build_space.import_check(Path(tmp))

    def test_the_import_check_stops_on_a_piece_left_out(self):
        for left_out, named in (("valuescale/method.py", "'method'"),
                                ("valuescale/calibration/protein-v1.json", "protein-v1")):
            with self.subTest(left_out=left_out), tempfile.TemporaryDirectory() as tmp:
                build_space = self._staged(tmp, leave_out=(left_out,))
                with self.assertRaises(SystemExit) as caught:
                    build_space.import_check(Path(tmp))
                self.assertIn(named, str(caught.exception))


if __name__ == "__main__":
    unittest.main()
