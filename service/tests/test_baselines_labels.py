"""benchmark/baselines_corrected.py --labels: the corrected baselines on a
candidate model's own reference labels (research/benchmark/protocol-sorted-cd4cd8.md,
rule 4). The join must be by cell and must refuse a misaligned table."""
import unittest

import numpy as np
import pandas as pd

from benchmark import baselines_corrected as bc
from benchmark import baselines_inputs


def table(original, clean):
    return pd.DataFrame({"cell": [f"c{i}" for i in range(len(original))],
                         "class_original": original, "class_clean": clean})


class RelabelTests(unittest.TestCase):
    def test_cells_take_their_new_class_by_orig_index(self):
        meta = pd.DataFrame({"orig_index": [2, 0], "class_name": ["nk", "cd8"]})
        labels = table(["cd8", "b", "nk"], ["nk", "b", "nk"])
        self.assertEqual(bc.relabel(meta, labels).tolist(), ["nk", "nk"])

    def test_a_table_in_another_cell_order_is_refused(self):
        meta = pd.DataFrame({"orig_index": [0, 1], "class_name": ["cd8", "b"]})
        with self.assertRaisesRegex(ValueError, "original class differs"):
            bc.relabel(meta, table(["b", "cd8"], ["b", "cd8"]))

    def test_a_table_too_short_is_refused(self):
        meta = pd.DataFrame({"orig_index": [0, 5], "class_name": ["cd8", "b"]})
        with self.assertRaisesRegex(ValueError, "orig_index runs to 5"):
            bc.relabel(meta, table(["cd8"], ["cd8"]))

    def test_other_label_sets_never_write_over_the_original_runs(self):
        self.assertEqual(bc.out_dir("original"), bc.OUT)
        for name in ("clean", "v51", "v52"):
            self.assertNotEqual(bc.out_dir(name), bc.OUT)
            self.assertIn(name, bc.out_dir(name).name)

    def test_every_committed_label_set_joins_the_benchmark_reference(self):
        """The real tables against the benchmark's RNA cells (local data: skipped
        where benchmark/results/rna_meta.csv is not built)."""
        meta_path = baselines_inputs.D / "rna_meta.csv"
        if not meta_path.exists():
            self.skipTest("benchmark/results/rna_meta.csv is not built here")
        meta = pd.read_csv(meta_path)
        for name, path in bc.LABEL_SETS.items():
            if path is None:
                continue
            with self.subTest(labels=name):
                new = bc.relabel(meta, pd.read_csv(path))
                self.assertEqual(len(new), len(meta))
                changed = int((new != meta["class_name"].to_numpy()).sum())
                self.assertGreater(changed, 0)
                self.assertTrue(np.all(pd.notna(new)))


if __name__ == "__main__":
    unittest.main()
