import unittest

from service.pipeline import alignment, gene_ids, validation


def _tiny_map():
    return gene_ids.GeneIdMap(
        symbol_to_feature={"A1BG": "A1BG", "TP53": "TP53", "EGFR": "EGFR"},
        ensembl_to_feature={},
        uniprot_to_feature={},
        feature_genes=frozenset({"A1BG", "TP53", "EGFR"}),
    )


def _raw(gene_names, cell_ids, n_values_per_gene=None):
    n_cells = len(cell_ids)
    values = [[float(i + j) for j in range(n_cells)] for i in range(len(gene_names))]
    import numpy as np
    return alignment.RawMatrix(gene_names=gene_names, cell_ids=cell_ids, values=np.array(values))


class ValidateOrientationTests(unittest.TestCase):
    def test_correctly_oriented_upload_passes(self):
        raw = _raw(["A1BG", "TP53", "EGFR"], ["cell_1", "cell_2", "cell_3"])
        validation.validate_orientation(raw, _tiny_map())  # should not raise

    def test_transposed_upload_is_rejected(self):
        # Genes and cell IDs swapped: "gene_names" are now cell-like strings,
        # "cell_ids" are now real gene symbols.
        raw = _raw(["cell_1", "cell_2", "cell_3"], ["A1BG", "TP53", "EGFR"])
        with self.assertRaises(validation.ValidationError):
            validation.validate_orientation(raw, _tiny_map())

    def test_neither_side_matching_anything_does_not_raise(self):
        # No signal either way -- refusing here would block legitimate
        # uploads using identifiers outside the map; only a clear reversal
        # (cell side matching as well as or better than the gene side) is
        # refused.
        raw = _raw(["nope1", "nope2"], ["also_nope1", "also_nope2"])
        validation.validate_orientation(raw, _tiny_map())


class ValidateCellCountTests(unittest.TestCase):
    def test_below_refuse_threshold_raises(self):
        raw = _raw(["A1BG"], [f"c{i}" for i in range(19)])
        with self.assertRaises(validation.ValidationError):
            validation.validate_cell_count(raw)

    def test_at_refuse_threshold_does_not_raise(self):
        raw = _raw(["A1BG"], [f"c{i}" for i in range(20)])
        warnings = validation.validate_cell_count(raw)
        self.assertTrue(warnings.low_cell_count)  # still below the warn threshold

    def test_at_warn_threshold_has_no_warning(self):
        raw = _raw(["A1BG"], [f"c{i}" for i in range(100)])
        warnings = validation.validate_cell_count(raw)
        self.assertFalse(warnings.low_cell_count)

    def test_above_warn_threshold_has_no_warning(self):
        raw = _raw(["A1BG"], [f"c{i}" for i in range(500)])
        warnings = validation.validate_cell_count(raw)
        self.assertFalse(warnings.low_cell_count)


class ValidateValuesTests(unittest.TestCase):
    """A table with no observed value is refused in words (R1 of protein v2,
    research/value-scale-v2-plan.md): before, it was answered with every cell
    left without an answer, or, a table of 0s under the median rule, with a
    label for every cell."""

    def _filled(self, *entries):
        import numpy as np
        cells = [f"c{i}" for i in range(25)]
        values = np.resize(np.array(entries, dtype=float), (3, len(cells)))
        return alignment.RawMatrix(gene_names=["A1BG", "TP53", "EGFR"], cell_ids=cells, values=values)

    def test_every_entry_empty_or_0_is_refused_saying_why(self):
        import numpy as np
        for entries in ((np.nan,), (0.0,), (np.nan, 0.0), (np.inf, -np.inf, 0.0)):
            with self.assertRaises(validation.ValidationError) as caught:
                validation.validate_values(self._filled(*entries))
            self.assertEqual(str(caught.exception), validation.NO_VALUES)
        self.assertIn("empty or 0", validation.NO_VALUES)

    def test_one_observed_value_is_enough_and_a_negative_one_counts(self):
        import numpy as np
        validation.validate_values(self._filled(np.nan, 0.0, 0.0, 7.5))
        validation.validate_values(self._filled(np.nan, -1.2))

    def test_validate_refuses_it_after_the_cell_count(self):
        import numpy as np
        with self.assertRaises(validation.ValidationError) as caught:
            validation.validate(self._filled(np.nan), _tiny_map())
        self.assertEqual(str(caught.exception), validation.NO_VALUES)
        few = alignment.RawMatrix(gene_names=["A1BG"], cell_ids=["c1", "c2"], values=np.full((1, 2), np.nan))
        with self.assertRaises(validation.ValidationError) as caught:
            validation.validate(few, _tiny_map())
        self.assertIn("at least 20", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
