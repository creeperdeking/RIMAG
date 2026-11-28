import unittest

import numpy as np

from common_lib.weight_window_bounds import (
    clamp_weight_window_span,
    extend_weight_window_frontier,
    followable_decades,
)


def _pair(lowers):
    lo = np.asarray(lowers, dtype=float)
    if lo.ndim == 1:
        lo = lo[:, None]
    up = np.where(lo > 0.0, lo * 3.0, 0.0)
    return lo, up


class WeightWindowBoundsTest(unittest.TestCase):
    def test_budget_leaves_two_splits_for_the_frontier(self):
        self.assertEqual(followable_decades(100, 10, 2), 8)

    def test_clamp_raises_only_the_deep_tail_and_keeps_the_window_width(self):
        lo, up = _pair([[0.5, 1e-4], [1e-18, 1e-16]])
        out_lo, out_up, raised = clamp_weight_window_span(lo, up)
        floor = 0.5 / 1e8
        self.assertEqual(raised, 2)
        self.assertAlmostEqual(out_lo[1, 0], floor)
        self.assertAlmostEqual(out_lo[1, 1], floor)
        self.assertAlmostEqual(out_up[1, 0] / out_lo[1, 0], 3.0)
        self.assertAlmostEqual(out_lo[0, 0], 0.5)
        self.assertAlmostEqual(out_lo[0, 1], 1e-4)

    def test_clamp_is_idempotent(self):
        lo, up = _pair([0.5, 1e-12, 1e-18])
        once_lo, once_up, raised = clamp_weight_window_span(lo, up)
        twice_lo, twice_up, again = clamp_weight_window_span(once_lo, once_up)
        self.assertGreater(raised, 0)
        self.assertEqual(again, 0)
        self.assertTrue(np.allclose(twice_lo, once_lo))
        self.assertTrue(np.allclose(twice_up, once_up))

    def test_shallow_map_is_left_alone(self):
        lo, up = _pair([0.5, 1e-4, 1e-6])
        out_lo, out_up, raised = clamp_weight_window_span(lo, up)
        self.assertEqual(raised, 0)
        self.assertTrue(np.allclose(out_lo, lo))
        self.assertTrue(np.allclose(out_up, up))

    def test_lip_advances_one_mesh_step_and_does_not_wrap(self):
        lo, up = _pair([0.5, 0.0, 0.0, 0.0])
        out_lo, _, added = extend_weight_window_frontier(lo, up)
        self.assertEqual(added, 1)
        self.assertAlmostEqual(out_lo[1, 0], 0.05)
        self.assertEqual(out_lo[2, 0], 0.0)
        self.assertEqual(out_lo[3, 0], 0.0)

    def test_lip_grows_from_the_deep_edge_not_from_the_fuel(self):
        lo, up = _pair([0.0, 0.5, 0.05, 0.005, 0.0])
        out_lo, out_up, added = extend_weight_window_frontier(lo, up)
        self.assertEqual(added, 1)
        self.assertEqual(out_lo[0, 0], 0.0)
        self.assertAlmostEqual(out_lo[4, 0], 0.0005)
        self.assertAlmostEqual(out_up[4, 0] / out_lo[4, 0], 3.0)

    def test_lip_does_not_fill_a_hole_back_toward_the_source(self):
        lo, up = _pair([0.5, 0.0, 1e-8])
        out_lo, _, added = extend_weight_window_frontier(lo, up)
        self.assertEqual(added, 0)
        self.assertEqual(out_lo[1, 0], 0.0)

    def test_lip_is_face_neighbors_only(self):
        lo = np.zeros((3, 3, 1))
        up = np.zeros((3, 3, 1))
        lo[1, 1, 0] = 0.5
        up[1, 1, 0] = 1.5
        out_lo, _, added = extend_weight_window_frontier(lo, up)
        self.assertEqual(added, 4)
        self.assertAlmostEqual(out_lo[1, 0, 0], 0.05)
        self.assertAlmostEqual(out_lo[0, 1, 0], 0.05)
        self.assertAlmostEqual(out_lo[1, 2, 0], 0.05)
        self.assertAlmostEqual(out_lo[2, 1, 0], 0.05)
        self.assertEqual(out_lo[0, 0, 0], 0.0)
        self.assertEqual(out_lo[2, 2, 0], 0.0)

    def test_saving_a_shallow_lip_would_walk_another_cell(self):
        # A lip beside a high window sits above the clamp floor, so a later
        # clamp keeps it and the next transport call treats it as scored.
        lo, up = _pair([0.5, 0.0, 0.0])
        lip_lo, lip_up, added = extend_weight_window_frontier(lo, up)
        self.assertEqual(added, 1)
        kept_lo, kept_up, raised = clamp_weight_window_span(lip_lo, lip_up)
        self.assertEqual(raised, 0)
        self.assertAlmostEqual(kept_lo[1, 0], 0.05)
        again_lo, _, added_again = extend_weight_window_frontier(kept_lo, kept_up)
        self.assertEqual(added_again, 1)
        self.assertAlmostEqual(again_lo[2, 0], 0.005)

    def test_saving_a_deep_lip_would_count_it_as_scored(self):
        lo, up = _pair([0.5, 0.5 / 1e8, 0.0])
        lip_lo, lip_up, added = extend_weight_window_frontier(lo, up)
        self.assertEqual(added, 1)
        self.assertAlmostEqual(lip_lo[2, 0], 0.5 / 1e9)
        kept_lo, _, raised = clamp_weight_window_span(lip_lo, lip_up)
        self.assertEqual(raised, 1)
        self.assertAlmostEqual(kept_lo[2, 0], 0.5 / 1e8)


if __name__ == "__main__":
    unittest.main()
