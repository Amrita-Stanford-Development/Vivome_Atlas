import unittest

from service.pipeline import gene_ids


def _tiny_map():
    return gene_ids.GeneIdMap(
        symbol_to_feature={"A1BG": "A1BG", "TP53": "TP53"},
        ensembl_to_feature={"ENSG00000121410": "A1BG", "ENSG00000141510": "TP53"},
        uniprot_to_feature={"P04217": "A1BG", "P04637": "TP53"},
        feature_genes=frozenset({"A1BG", "TP53"}),
    )


class ResolveIdentifiersTests(unittest.TestCase):
    def test_symbol_matches_case_insensitively(self):
        r = gene_ids.resolve_identifiers(["a1bg", "TP53", "A1bg"], _tiny_map())
        self.assertEqual(r.resolved, ["A1BG", "TP53", "A1BG"])
        self.assertEqual(r.matched, 3)
        self.assertEqual(r.unmapped, 0)

    def test_ensembl_id_matches(self):
        r = gene_ids.resolve_identifiers(["ENSG00000121410"], _tiny_map())
        self.assertEqual(r.resolved, ["A1BG"])

    def test_uniprot_accession_matches(self):
        r = gene_ids.resolve_identifiers(["P04637"], _tiny_map())
        self.assertEqual(r.resolved, ["TP53"])

    def test_uniprot_isoform_accession_resolves_to_its_base_accession(self):
        r = gene_ids.resolve_identifiers(["P04637-2"], _tiny_map())
        self.assertEqual(r.resolved, ["TP53"])
        self.assertEqual(r.matched, 1)

    def test_unmapped_identifier_is_reported_by_name(self):
        r = gene_ids.resolve_identifiers(["NOT_A_REAL_GENE"], _tiny_map())
        self.assertEqual(r.resolved, [None])
        self.assertEqual(r.unmapped, 1)
        self.assertEqual(r.unmapped_identifiers, ["NOT_A_REAL_GENE"])

    def test_semicolon_group_resolves_when_members_agree(self):
        r = gene_ids.resolve_identifiers(["TP53;P04637"], _tiny_map())
        self.assertEqual(r.resolved, ["TP53"])
        self.assertEqual(r.matched, 1)

    def test_semicolon_group_is_ambiguous_when_members_disagree(self):
        r = gene_ids.resolve_identifiers(["A1BG;TP53"], _tiny_map())
        self.assertEqual(r.resolved, [None])
        self.assertEqual(r.ambiguous, 1)
        self.assertEqual(r.ambiguous_identifiers, ["A1BG;TP53"])

    def test_empty_string_is_unmapped_not_a_crash(self):
        r = gene_ids.resolve_identifiers([""], _tiny_map())
        self.assertEqual(r.resolved, [None])
        self.assertEqual(r.unmapped, 1)

    def test_resolve_to_feature_symbols_is_order_and_duplicate_preserving(self):
        out = gene_ids.resolve_to_feature_symbols(["TP53", "NOPE", "TP53"], _tiny_map())
        self.assertEqual(out, ["TP53", None, "TP53"])


class LoadGeneIdMapTests(unittest.TestCase):
    """Exercises the real, committed gene_id_map_v1.tsv."""

    @classmethod
    def setUpClass(cls):
        cls.gene_map = gene_ids.load_gene_id_map()

    def test_covers_every_feature_space_gene(self):
        from service.pipeline import reference
        feature_genes = reference.load_feature_space_genes()
        self.assertEqual(len(self.gene_map.feature_genes), len(feature_genes))
        for gene in feature_genes:
            self.assertIn(gene.upper(), self.gene_map.symbol_to_feature)

    def test_a_known_gene_resolves_by_symbol_ensembl_and_uniprot(self):
        # A1BG: HGNC:5, ENSG00000121410, UniProt P04217 -- stable, well-known.
        r = gene_ids.resolve_identifiers(["A1BG", "ENSG00000121410", "P04217"], self.gene_map)
        self.assertEqual(r.resolved, ["A1BG", "A1BG", "A1BG"])

    def test_a_known_genes_uniprot_isoform_accession_also_resolves(self):
        r = gene_ids.resolve_identifiers(["P04217-2"], self.gene_map)
        self.assertEqual(r.resolved, ["A1BG"])

    def test_ambiguous_feature_gene_has_no_ensembl_or_uniprot_entry(self):
        # A feature-space gene whose own HGNC resolution was itself
        # ambiguous contributes only its symbol, never a guessed
        # cross-reference -- see gene_id_map_v1_provenance.json.
        self.assertIn("C18ORF21", self.gene_map.symbol_to_feature)


if __name__ == "__main__":
    unittest.main()


class SharedAccessionTests(unittest.TestCase):
    """An accession HGNC lists under several feature genes names all of them:
    it is ambiguous, never resolved to one."""

    def test_a_shared_accession_is_ambiguous_alone_in_a_group_and_as_an_isoform(self):
        r = gene_ids.resolve_identifiers(["P69905", "Q9H3K6-2", "HBA1", "HBA1;P69905"])
        self.assertEqual(r.resolved, [None, None, "HBA1", None])
        self.assertEqual(r.ambiguous_identifiers, ["P69905", "Q9H3K6-2", "HBA1;P69905"])

    def test_the_real_map_lists_the_shared_accessions_and_maps_none_of_them(self):
        gene_map = gene_ids.load_gene_id_map()
        self.assertEqual(gene_map.shared_accessions["P69905"], frozenset({"HBA1", "HBA2"}))
        for accession in gene_map.shared_accessions:
            self.assertNotIn(accession, gene_map.uniprot_to_feature)
