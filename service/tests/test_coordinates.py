import unittest

import numpy as np

from service.pipeline import coordinates


class FitPca3dTests(unittest.TestCase):
    def test_projects_pure_3d_variance_data_losslessly_up_to_rotation(self):
        rng = np.random.default_rng(0)
        true_3d = rng.normal(size=(500, 3)) * [10.0, 3.0, 1.0]
        embed = np.zeros((500, 10))
        embed[:, :3] = true_3d  # all variance lives in the first 3 axes

        pca = coordinates.fit_pca_3d(embed)
        projected = pca.project(embed)

        # Total variance should be preserved (no variance was in axes 3-9).
        self.assertAlmostEqual(projected.var(axis=0).sum(), true_3d.var(axis=0).sum(), delta=1e-3)

    def test_output_shape(self):
        rng = np.random.default_rng(1)
        embed = rng.normal(size=(40, 16))
        pca = coordinates.fit_pca_3d(embed)
        projected = pca.project(embed[:5])
        self.assertEqual(projected.shape, (5, 3))

    def test_a_query_point_at_the_reference_mean_projects_near_the_origin(self):
        rng = np.random.default_rng(2)
        embed = rng.normal(size=(200, 5))
        pca = coordinates.fit_pca_3d(embed)
        projected = pca.project(embed.mean(axis=0, keepdims=True))
        np.testing.assert_allclose(projected, np.zeros((1, 3)), atol=1e-5)


if __name__ == "__main__":
    unittest.main()
