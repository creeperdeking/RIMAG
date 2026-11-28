"""Keep MAGIC weight windows inside what one history is allowed to split.

OpenMC adds the split factor (between 2 and max_split) to a counter on the
particle and refuses another split once that counter reaches
max_history_splits. Daughters inherit the counter, so the whole family shares
one budget. With max_split 10 and a cap of 100 that budget is about ten
factor-of-ten splits.

max_lower_bound_ratio does not cap a single bin. The first window more than
that ratio below the particle sets one scale, and every later window is
multiplied by it, so the history stops splitting. Leave the ratio at 1.

A saved map deeper than the budget spends every split before the frontier.
The bins past that stay empty, and the next pass redraws the same cliff.
Clamp the saved bounds so a history can follow them and still have splits
left. When the map is loaded for transport, give each empty face-neighbor of the
deep edge a window one split below that edge. The history then splits
once into that cell, MAGIC can score it, and the frontier moves one mesh cell.
Do not write that lip back to disk: clamping it on the next save would treat
it as scored and walk another cell without any new tallies. Do not paste the
previous pass's bounds into empty bins either; those belong to a different
flux map.
"""

from __future__ import annotations

import numpy as np

# Matches the cap written to settings.xml for seed, refine, and use.
DEFAULT_HISTORY_SPLITS = 100
DEFAULT_MAX_SPLIT = 10
# Held back from the saved map so transport can still pay for the lip.
DEFAULT_RESERVE_SPLITS = 2


def followable_decades(
    history_splits: int = DEFAULT_HISTORY_SPLITS,
    max_split: int = DEFAULT_MAX_SPLIT,
    reserve: int = DEFAULT_RESERVE_SPLITS,
) -> int:
    """How many factor-of-max_split steps a history can follow in a saved map."""
    factor = max(2, int(max_split))
    events = int(history_splits) // factor - int(reserve)
    return max(1, events)


def _bounds(lower, upper) -> tuple[np.ndarray, np.ndarray]:
    lo = np.array(lower, dtype=float, copy=True)
    up = np.array(upper, dtype=float, copy=True)
    if lo.shape != up.shape or lo.ndim < 2:
        raise ValueError(
            "lower and upper weight-window bounds must share a shape (..., energy)"
        )
    return lo, up


def _valid_windows(lo: np.ndarray, up: np.ndarray) -> np.ndarray:
    """Bins MAGIC actually scored: a positive lower bound and an upper above it."""
    valid = np.isfinite(lo) & (lo > 0.0)
    broken = valid & ~(np.isfinite(up) & (up > lo))
    up[broken] = lo[broken] * 3.0
    return valid


def clamp_weight_window_span(
    lower,
    upper,
    *,
    history_splits: int = DEFAULT_HISTORY_SPLITS,
    max_split: int = DEFAULT_MAX_SPLIT,
    reserve: int = DEFAULT_RESERVE_SPLITS,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Raise bounds that are deeper than the split budget.

    The floor is one global value, the peak lower bound divided by
    ``max_split ** followable_decades``. A neutron can change energy group
    along a flight, so a quiet group is not allowed to sit decades below the
    rest of the map. Upper bounds scale with the lower bounds, which keeps
    each window's width. Returns the new arrays and how many bins were raised.
    Applying this twice changes nothing.
    """
    lo, up = _bounds(lower, upper)
    factor = max(2, int(max_split))
    decades = followable_decades(history_splits, factor, reserve)
    valid = _valid_windows(lo, up)
    if not np.any(valid):
        return lo, up, 0
    peak = float(lo[valid].max())
    floor = peak / float(factor) ** decades
    deep = valid & (lo < floor)
    raised = int(np.count_nonzero(deep))
    if raised:
        scale = floor / lo[deep]
        lo[deep] = floor
        up[deep] = up[deep] * scale
    return lo, up, raised


def _frontier_bins(lo_e: np.ndarray, scored: np.ndarray) -> np.ndarray:
    """Scored bins that have no strictly deeper scored face neighbor.

    The source region fails this test, so an empty cell beside the fuel does
    not grow a window. The deep edge passes it, including a flat plateau.
    """
    frontier = np.array(scored, copy=True)
    for axis in range(lo_e.ndim):
        for shift in (-1, 1):
            n_lo = np.roll(lo_e, shift, axis=axis)
            n_scored = np.roll(scored, shift, axis=axis)
            edge = [slice(None)] * lo_e.ndim
            edge[axis] = 0 if shift == 1 else -1
            n_scored[tuple(edge)] = False
            frontier &= ~(n_scored & (n_lo < lo_e))
    return frontier


def extend_weight_window_frontier(
    lower,
    upper,
    *,
    max_split: int = DEFAULT_MAX_SPLIT,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Put a one-split window on empty face-neighbors of the deep edge.

    Only bins with no deeper scored neighbor seed the lip, so the halo grows
    past the frontier and not sideways out of the fuel. An empty cell that
    also touches a window more than one split higher is a hole back toward
    the source and stays empty: a lip there would consume the whole budget.
    Corners stay empty,
    and the mesh does not wrap, so one call advances the frontier by a single
    mesh step. The new window continues the deepest such neighbor and keeps
    that neighbor's upper/lower ratio.
    """
    lo, up = _bounds(lower, upper)
    factor = float(max(2, int(max_split)))
    added = 0
    for energy in range(lo.shape[-1]):
        lo_e = lo[..., energy]
        up_e = up[..., energy]
        scored = _valid_windows(lo_e, up_e)
        if not np.any(scored):
            continue
        frontier = _frontier_bins(lo_e, scored)
        best_lo = np.full(lo_e.shape, np.inf)
        best_ratio = np.ones(lo_e.shape, dtype=float)
        high_lo = np.zeros(lo_e.shape, dtype=float)
        for axis in range(lo_e.ndim):
            for shift in (-1, 1):
                n_lo = np.roll(lo_e, shift, axis=axis)
                n_up = np.roll(up_e, shift, axis=axis)
                n_scored = np.roll(scored, shift, axis=axis)
                n_frontier = np.roll(frontier, shift, axis=axis)
                edge = [slice(None)] * lo_e.ndim
                edge[axis] = 0 if shift == 1 else -1
                n_scored[tuple(edge)] = False
                n_frontier[tuple(edge)] = False
                high_lo = np.maximum(high_lo, np.where(n_scored, n_lo, 0.0))
                n_edge = np.where(n_frontier, n_lo, np.inf)
                deeper = n_edge < best_lo
                ratio = np.ones(lo_e.shape, dtype=float)
                np.divide(
                    n_up,
                    np.where(n_frontier, n_lo, 1.0),
                    out=ratio,
                    where=n_frontier & (n_lo > 0.0),
                )
                best_lo = np.where(deeper, n_edge, best_lo)
                best_ratio = np.where(deeper, ratio, best_ratio)
        # A hole between the deep edge and a much higher window would make a
        # heavy particle split until the budget ran out. Only cells whose
        # scored neighbors all sit within one split of the edge get a lip.
        extend = (
            (~scored)
            & np.isfinite(best_lo)
            & (best_lo > 0.0)
            & (high_lo <= best_lo * factor)
        )
        count = int(np.count_nonzero(extend))
        if count == 0:
            continue
        added += count
        new_lo = best_lo[extend] / factor
        new_up = new_lo * np.maximum(best_ratio[extend], 1.0 + 1e-6)
        lo_e[extend] = new_lo
        up_e[extend] = new_up
    return lo, up, added
