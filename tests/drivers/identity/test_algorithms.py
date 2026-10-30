# Module name: tests/drivers/identity/test_algorithms.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""SyRS-DRV-identity §2.5: the algorithms on known values from their sources."""

from __future__ import annotations

import unittest

from wattleflow.drivers.identity.matching import (
    Blocking,
    Bridges,
    Decision,
    ExpectationMaximisation,
    FellegiSunter,
    LinkageQuality,
    UnionFind,
)
from wattleflow.drivers.identity.recognition import (
    CheckDigit,
    DateForms,
    EntityKinds,
    IdentityNormaliser,
    KeywordAutomaton,
)
from wattleflow.drivers.identity.similarity import (
    DamerauLevenshtein,
    Jaro,
    JaroWinkler,
    Levenshtein,
    NGramJaccard,
    Soundex,
    TfIdfCosine,
)


class ComparatorTest(unittest.TestCase):
    def test_levenshtein_distance(self):
        self.assertEqual(Levenshtein.distance("kitten", "sitting"), 3)

    def test_optimal_string_alignment_counts_a_swap_once(self):
        self.assertEqual(DamerauLevenshtein.distance("ca", "ac"), 1)
        self.assertEqual(Levenshtein.distance("ca", "ac"), 2)

    def test_jaro_and_jaro_winkler_reference_values(self):
        # Winkler (1990): MARTHA / MARHTA.
        self.assertAlmostEqual(Jaro.similarity("martha", "marhta"), 0.9444, places=4)
        self.assertAlmostEqual(JaroWinkler.similarity("martha", "marhta"), 0.9611, places=4)

    def test_jaccard_ignores_word_order(self):
        self.assertGreater(NGramJaccard.similarity("smith john", "john smith"), 0.6)

    def test_tfidf_cosine_of_equal_texts_is_one(self):
        self.assertAlmostEqual(TfIdfCosine.similarity("acme pty", "acme pty"), 1.0)

    def test_soundex_reference_codes(self):
        self.assertEqual(Soundex.encode("Robert"), "R163")
        self.assertEqual(Soundex.encode("Rupert"), "R163")
        self.assertEqual(Soundex.encode("Ashcraft"), "A261")


class RecognitionHelpersTest(unittest.TestCase):
    def test_check_digits(self):
        self.assertTrue(CheckDigit.tfn("123456782"))
        self.assertFalse(CheckDigit.tfn("123456789"))
        self.assertTrue(CheckDigit.abn("51824753556"))
        self.assertTrue(CheckDigit.oib("12345678903"))
        self.assertTrue(CheckDigit.iban("GB82 WEST 1234 5698 7654 32"))
        self.assertTrue(CheckDigit.luhn("4111111111111111"))

    def test_dates_become_iso_8601(self):
        self.assertEqual(DateForms.iso("3 March 1980"), "1980-03-03")
        self.assertEqual(DateForms.iso("March 3, 1980"), "1980-03-03")
        self.assertIsNone(DateForms.iso("31/13/2020"))

    def test_normalisation(self):
        self.assertEqual(IdentityNormaliser.value("PER", "Dr. Zoë  O'Brien", ["Dr"]), "zoe o brien")
        self.assertEqual(IdentityNormaliser.value("TEL", "+61 (2) 9876-5432"), "+61298765432")

    def test_the_kind_list_is_closed(self):
        self.assertEqual(len(EntityKinds.all()), 38)
        self.assertEqual(EntityKinds.unknown(["PER", "XYZ"]), ["XYZ"])

    def test_automaton_finds_whole_words_only(self):
        found = KeywordAutomaton({"ann lee": "PER"}, level=50).find("Ann Lee and Joann Leeds")
        self.assertEqual(found, [(0, 7, "PER")])


class ModelTest(unittest.TestCase):
    def test_an_unlearned_model_returns_the_prior(self):
        zeros = {"c": [0, 0]}
        model = FellegiSunter(zeros, zeros, 0.2, level=50)
        self.assertAlmostEqual(model.probability({"c": 0}), 0.2)

    def test_weights_are_monotone(self):
        model = FellegiSunter({"c": [1, 9, 0]}, {"c": [9, 1, 0]}, 0.5, level=50)
        w = model.weights("c")
        self.assertGreaterEqual(w[0], w[1])
        self.assertGreaterEqual(w[1], w[2])

    def test_em_separates_matches_from_non_matches(self):
        vectors = [{"c": 0}] * 20 + [{"c": 1}] * 80
        m, u, lam = ExpectationMaximisation.estimate(vectors, {"c": 2}, 0.5, 20)
        self.assertGreater(m["c"][0], u["c"][0])

    def test_two_thresholds(self):
        self.assertEqual(Decision.decide([("a", 0.95)], 0.9, 0.6), ("known", "a"))
        self.assertEqual(Decision.decide([("a", 0.7)], 0.9, 0.6), ("uncertain", None))
        self.assertEqual(Decision.decide([("a", 0.3)], 0.9, 0.6), ("new", None))
        self.assertEqual(Decision.decide([("a", 0.95), ("b", 0.92)], 0.9, 0.6)[0], "uncertain")

    def test_blocking_keys(self):
        self.assertIn("s:S530", Blocking.keys("john smith"))


class GroupingTest(unittest.TestCase):
    def test_union_find_groups(self):
        uf = UnionFind(4, level=50)
        self.assertEqual(sorted(uf.algorithm(None, pairs=[(0, 1), (2, 3)]).values()), [[0, 1], [2, 3]])

    def test_bridges(self):
        # A triangle 0-1-2 joined to 3 by one edge: only 2-3 is a bridge.
        self.assertEqual(Bridges.find(4, [(0, 1), (1, 2), (2, 0), (2, 3)]), {(2, 3)})

    def test_quality(self):
        q = LinkageQuality.measure([(1, 2), (3, 4)], [(2, 1), (5, 6)])
        self.assertEqual((q["precision"], q["recall"]), (0.5, 0.5))


if __name__ == "__main__":
    unittest.main()
