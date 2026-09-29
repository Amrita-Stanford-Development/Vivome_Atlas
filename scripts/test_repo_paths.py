import unittest

import check_paths


class RepoPathsTests(unittest.TestCase):
    """Runs scripts/check_paths.py as part of the normal test run, so a moved
    file can't leave a broken citation, link or LFS entry behind."""

    def test_every_cited_path_resolves(self):
        problems = check_paths.find_problems()
        self.assertEqual(problems, [], "\n" + "\n".join(problems))


if __name__ == "__main__":
    unittest.main()
