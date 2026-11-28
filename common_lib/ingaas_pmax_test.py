"""Numeric checks for the Wang Pmax post-process. No OpenMC."""

import math
import unittest

from common_lib.ingaas_pmax import (
    K_BASELINE,
    K_FAST,
    K_TRUNCATED,
    MODEL_INGAAS_M_G_MOL,
    WANG_C,
    WANG_D_M2,
    format_pmax_lines,
    model_ingaas_atoms,
    pmax_from_damage,
    remaining_pmax,
)


class IngaasPmaxTest(unittest.TestCase):
    def test_ten_percent_loss_fluence(self):
        fluence = WANG_D_M2 * (math.exp(0.1 / WANG_C) - 1.0)
        self.assertAlmostEqual(remaining_pmax(fluence), 0.9, places=9)

    def test_damage_energy_matches_the_fluence_form(self):
        fluence = 1.0e16
        atoms = 1.0e24
        source = 1.0e10
        seconds = 1.0
        accumulated = fluence * K_BASELINE
        td = accumulated * atoms / (source * seconds)
        report = pmax_from_damage(td, 0.0, source, atoms, seconds)
        self.assertIsNotNone(report)
        self.assertAlmostEqual(report["fluence_m2"], fluence, places=6)
        self.assertAlmostEqual(report["remaining"], remaining_pmax(fluence), places=12)
        self.assertEqual(report["ci95_pct"], 0.0)
        self.assertFalse(report["outside"])
        self.assertGreater(report["fast_remaining"], report["remaining"])
        self.assertGreater(report["truncated_remaining"], report["remaining"])
        self.assertGreater(report["fast_remaining"], report["truncated_remaining"])

    def test_larger_reference_cross_section_lowers_the_equivalent_fluence(self):
        self.assertGreater(K_FAST, K_TRUNCATED)
        self.assertGreater(K_TRUNCATED, K_BASELINE)

    def test_atom_count_uses_model_formula_units(self):
        atoms = model_ingaas_atoms(1.0, 5.50)
        expected = 2.0 * 5.50 * 6.02214076e23 / MODEL_INGAAS_M_G_MOL
        self.assertAlmostEqual(atoms, expected, places=3)
        self.assertTrue(math.isnan(model_ingaas_atoms(0.0, 5.50)))

    def test_printed_line_marks_extrapolation(self):
        report = pmax_from_damage(1.0, 0.1, 1.0e20, 1.0e20, 1.0e8)
        self.assertIsNotNone(report)
        self.assertTrue(report["outside"])
        main, sensitivity = format_pmax_lines(report, 10.0)
        self.assertIn("outside measured range", main)
        self.assertIn("fast-fluence", sensitivity)
        self.assertTrue(main.startswith("InGaAs Pmax remaining:"))


if __name__ == "__main__":
    unittest.main()
