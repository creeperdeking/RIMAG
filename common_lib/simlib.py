import gc
import glob
import openmc
import openmc.deplete
import os
import time
from pathlib import Path
from typing import List, Dict, Literal
from tabulate import tabulate
import json
import scipy.constants as cst
from common_lib.materials import MonitoredNuclide
import numpy as np
import h5py
import math
import re
import sys
from common_lib.geometry_utils import get_geometry_bounding_box
from common_lib.geometry_types import GeometrySettings
from common_lib.tallies import (
    create_C14_production_tally,
    create_tritium_production_tally,
    create_O16_activation_tally,
    create_dpa_tally,
    create_emitter_tally,
    create_energy_deposition_tallies,
    create_fission_energy_weighted_flux_tally,
    create_flux_band_tally,
    create_photovoltaic_flux_tally,
    create_photovoltaic_heating_absorption_tally,
    print_tallies,
)
from one_layer_disk_design.disks_core_characteristics import CoreCharacteristics


def clean_directory():
    patternlist = [
        "materials.xml",
        "settings.xml",
        "tallies.xml",
        "geometry.xml",
        "summary.h5",
        "particle*.h5",
        "particle*.h5",
        "statepoint*.h5",
        "openmc_*.h5",
    ]
    for pattern in patternlist:
        filelist = glob.glob(pattern)
        for file in filelist:
            try:
                os.remove(file)
            except OSError as e:
                pass


def clean_xml():
    patternlist = [
        "materials.xml",
        "settings.xml",
        "tallies.xml",
        "geometry.xml",
    ]
    for pattern in patternlist:
        filelist = glob.glob(pattern)
        for file in filelist:
            try:
                os.remove(file)
            except OSError as e:
                pass


def generate_XML(geometry, settings, tallies, materials_dict):
    clean_xml()
    materials = openmc.Materials(materials_dict.values())

    materials.export_to_xml()
    geometry.export_to_xml()
    settings.export_to_xml()

    if tallies is not None:
        tallies.export_to_xml()


def _get_threads_from_settings(default_threads: int = 20) -> int:
    """
    Read the number of threads from simsettings.json located in the current
    working directory (where Python was executed).
    Falls back to default_threads if the file or value is unavailable/invalid.
    """
    try:
        settings_path = "simsettings.json"
        if not os.path.exists(settings_path):
            return default_threads
        with open(settings_path, "r") as f:
            data = json.load(f)
        threads = int(data.get("threads", default_threads))
        if threads <= 0:
            return default_threads
        return threads
    except Exception:
        return default_threads


def _format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


class _OpenMCProgressReporter:
    # OpenMC batch table: "batch/gen  k_instant  [k_avg +/- std]"
    _BATCH_GEN_RE = re.compile(
        r"^\s*(\d+)/(\d+)\s+([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)"
        r"(?:\s+([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)"
        r"\s+\+/-\s+([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?))?"
    )
    # Inactive batches skip tallies and usually finish ~2× faster than active ones.
    _INACTIVE_SPEEDUP = 2.0

    def __init__(
        self,
        total_batches: int | None,
        generations_per_batch: int,
        inactive_batches: int = 0,
    ):
        self.total_batches = total_batches
        self.generations_per_batch = generations_per_batch
        self.inactive_batches = max(0, int(inactive_batches or 0))
        self.total_steps = (
            total_batches * generations_per_batch if total_batches else None
        )
        self._output = sys.__stdout__
        self._start_time = time.time()
        self._last_render = 0.0
        self._current_step = 0
        self._last_k = None
        self._last_k_unc = None
        self._active = False
        self._lost_bc_warnings = 0

    def _step_weight(self, step: int) -> float:
        if step <= 0 or not self.generations_per_batch:
            return 1.0
        batch = (step - 1) // self.generations_per_batch + 1
        if batch <= self.inactive_batches:
            return 1.0 / self._INACTIVE_SPEEDUP
        return 1.0

    def _work_through(self, step: int) -> float:
        if not self.total_steps or step <= 0:
            return 0.0
        step = min(step, self.total_steps)
        inactive_steps = min(
            step, self.inactive_batches * self.generations_per_batch
        )
        active_steps = step - inactive_steps
        return inactive_steps / self._INACTIVE_SPEEDUP + active_steps

    def feed_line(self, line: str) -> None:
        if not line.strip():
            return

        if "K EIGENVALUE SIMULATION" in line:
            self._active = True
            return

        match = self._BATCH_GEN_RE.match(line)
        if match and self.total_steps:
            batch = int(match.group(1))
            generation = int(match.group(2))
            # Prefer the running average once OpenMC starts printing it.
            if match.group(4) is not None:
                self._last_k = match.group(4)
                self._last_k_unc = match.group(5)
            else:
                self._last_k = match.group(3)
                self._last_k_unc = None
            self._current_step = (batch - 1) * self.generations_per_batch + generation
            self._active = True
            self._render()
            return

        # Keep non-progress OpenMC output visible (RESULTS, warnings, …).
        # Rate-limit periodic-BC lost-particle spam: each line also tends to
        # coincide with expensive particle.h5 dumps and floods the SSE UI.
        if self._active and line.strip():
            if "Couldn't find particle after hitting periodic boundary" in line:
                self._lost_bc_warnings += 1
                n = self._lost_bc_warnings
                if n <= 5 or n % 200 == 0:
                    self._output.write(f"{line}  [#{n}]\n")
                    self._output.flush()
            else:
                self._output.write(line + "\n")
                self._output.flush()

        if self.total_steps is None:
            self._active = True
            now = time.time()
            if now - self._last_render >= 0.5:
                self._render_indeterminate()
                self._last_render = now

    def _render(self) -> None:
        if not self.total_steps:
            return

        done_work = self._work_through(self._current_step)
        total_work = self._work_through(self.total_steps)
        progress = min(done_work / total_work, 1.0) if total_work > 0 else 0.0
        elapsed = time.time() - self._start_time
        if done_work > 0:
            eta = elapsed * (total_work - done_work) / done_work
        else:
            eta = 0.0

        batch = (self._current_step - 1) // self.generations_per_batch + 1
        generation = (self._current_step - 1) % self.generations_per_batch + 1
        bar_width = 30
        filled = int(bar_width * progress)
        bar = "#" * filled + "-" * (bar_width - filled)
        phase = "inactive" if batch <= self.inactive_batches else "active"

        message = (
            f"[OpenMC] |{bar}| {progress * 100:5.1f}%  "
            f"batch {batch}/{self.total_batches}  "
            f"gen {generation}/{self.generations_per_batch}  "
            f"{phase}"
        )
        if self._last_k is not None:
            message += f"  k={self._last_k}"
            if self._last_k_unc is not None:
                message += f" +/- {self._last_k_unc}"
        message += f"  ETA {_format_duration(eta)}"
        # Newline (not \\r): the web SSE logger is line-based.
        self._output.write(message + "\n")
        self._output.flush()
        self._last_render = time.time()

    def _render_indeterminate(self) -> None:
        elapsed = time.time() - self._start_time
        self._output.write(
            f"[OpenMC] running... elapsed {_format_duration(elapsed)}\n"
        )
        self._output.flush()

    def finish(self) -> None:
        if self._lost_bc_warnings:
            self._output.write(
                f"[OpenMC] periodic-BC lost-particle warnings: "
                f"{self._lost_bc_warnings} total "
                f"(log rate-limited; see max_write_lost_particles)\n"
            )
            self._output.flush()
        if self._active:
            if self.total_steps and self._current_step > 0:
                self._render()
            elif self.total_steps is None:
                self._render_indeterminate()


class _OpenMCProgressStream:
    def __init__(self, reporter: _OpenMCProgressReporter):
        self._reporter = reporter
        self._buffer = ""

    def write(self, data: str) -> int:
        if not data:
            return 0
        self._buffer += data
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._reporter.feed_line(line)
        return len(data)

    def flush(self) -> None:
        if self._buffer:
            self._reporter.feed_line(self._buffer)
            self._buffer = ""

    def isatty(self) -> bool:
        return False


def run_sim(geometry, settings, materials_dict, tallies=None, quiet=False):
    generate_XML(geometry, settings, tallies, materials_dict)
    if settings.run_mode == "volume":
        print("[OpenMC] Running stochastic volume calculations...")
    threads = _get_threads_from_settings(default_threads=20)
    geometry_debug = settings.run_mode == "volume"
    if quiet:
        total_batches = getattr(settings, "batches", None)
        generations_per_batch = getattr(settings, "generations_per_batch", 10)
        inactive_batches = getattr(settings, "inactive", 0) or 0
        reporter = _OpenMCProgressReporter(
            total_batches, generations_per_batch, inactive_batches=inactive_batches
        )
        progress_stream = _OpenMCProgressStream(reporter)
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = progress_stream
        sys.stderr = progress_stream
        try:
            openmc.run(threads=threads, geometry_debug=geometry_debug)
        except RuntimeError as exc:
            msg = str(exc).split("Abort(")[0].strip()
            raise RuntimeError(msg) from exc
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            reporter.finish()
    else:
        openmc.run(threads=threads, geometry_debug=geometry_debug)
    # clean_directory()


WeightWindows = Literal["generate", "use", "no", "seed", "refine"]

WW_META_FILE = "weight_windows_meta.json"
WW_FILE = "weight_windows.h5"


def make_ww_mesh(
    lower_left_corner: tuple,
    upper_right_corner: tuple,
    cell_dimension: float = 10.0,
):
    cell = max(0.5, float(cell_dimension))
    ww_mesh = openmc.RegularMesh()
    dimension_x = max(
        int(math.ceil((upper_right_corner[0] - lower_left_corner[0]) / cell)), 1
    )
    dimension_y = max(
        int(math.ceil((upper_right_corner[1] - lower_left_corner[1]) / cell)), 1
    )
    dimension_z = max(
        int(math.ceil((upper_right_corner[2] - lower_left_corner[2]) / cell)), 1
    )
    ww_mesh.dimension = (dimension_x, dimension_y, dimension_z)
    ww_mesh.lower_left = lower_left_corner
    ww_mesh.upper_right = upper_right_corner
    print(
        f"Weight-window mesh {ww_mesh.dimension} "
        f"(~{cell:.2f} cm cells over "
        f"[{lower_left_corner[0]:.1f},{upper_right_corner[0]:.1f}] × "
        f"[{lower_left_corner[1]:.1f},{upper_right_corner[1]:.1f}] × "
        f"[{lower_left_corner[2]:.1f},{upper_right_corner[2]:.1f}] cm)"
    )
    return ww_mesh


def ww_energy_bounds(n_groups: int) -> np.ndarray:
    """Log-spaced neutron energy group edges from 1e-5 eV to 20 MeV."""
    groups = max(1, int(n_groups))
    return np.logspace(-5.0, math.log10(2.0e7), groups + 1)


def load_weight_windows_list(ww_path: str | Path = WW_FILE):
    """Load all WeightWindows sets from an HDF5 file."""
    path = Path(ww_path)
    if not path.is_file():
        raise FileNotFoundError(f"{path} not found")
    try:
        return openmc.WeightWindowsList.from_hdf5(str(path))
    except Exception:
        return openmc.hdf5_to_wws(str(path))


def latest_weight_windows(ww_path: str | Path = WW_FILE):
    """Return only the newest MAGIC set.

    Refine appends a new WeightWindows object beside the previous ones; transport
    and depth stats must use the last entry, not the original seed.
    """
    wws = load_weight_windows_list(ww_path)
    if not wws:
        raise ValueError(f"{ww_path} contains no weight windows")
    return wws[-1]


def prune_weight_windows_file(ww_path: str | Path = WW_FILE) -> int:
    """Keep only the latest WW set so refine does not stack forever."""
    path = Path(ww_path)
    wws = load_weight_windows_list(path)
    n = len(wws)
    if n <= 1:
        return n
    openmc.WeightWindowsList([wws[-1]]).export_to_hdf5(str(path))
    print(f"Weight windows: pruned {n} sets → 1 (kept latest)")
    return 1


def summarize_weight_windows(ww_path: str | Path = WW_FILE) -> dict:
    """Coverage / dynamic-range stats for a MAGIC weight-windows file.

    Used after seed/refine to judge how far windows have pushed into the shield:
    empty outer voxels and a small log-span mean another refine is needed.
    """
    path = Path(ww_path)
    wws = load_weight_windows_list(path)
    if not wws:
        raise ValueError(f"{path} contains no weight windows")

    # Always score the newest set (refine appends rather than replacing).
    ww = wws[-1]
    n_sets = len(wws)
    lo = np.asarray(ww.lower_ww_bounds, dtype=float)
    mesh = ww.mesh
    ll = np.asarray(mesh.lower_left, dtype=float)
    ur = np.asarray(mesh.upper_right, dtype=float)
    nx, ny, nz = (int(v) for v in mesh.dimension)
    # OpenMC stores (nx, ny, nz, n_energy).
    if lo.ndim != 4:
        lo = lo.reshape(nx, ny, nz, -1)
    positive = np.isfinite(lo) & (lo > 0.0)
    spatial_any = np.any(positive, axis=3)
    spatial_coverage = float(spatial_any.mean()) if spatial_any.size else 0.0
    energy_coverage = float(positive.mean()) if positive.size else 0.0

    decades = None
    lo_min = None
    lo_max = None
    if np.any(positive):
        vals = lo[positive]
        lo_min = float(vals.min())
        lo_max = float(vals.max())
        if lo_min > 0.0:
            decades = float(math.log10(lo_max / lo_min))

    # Outer-third of the XY mesh (by radius from mesh centre): proxy for shield/TPV.
    cx = 0.5 * (ll[0] + ur[0])
    cy = 0.5 * (ll[1] + ur[1])
    dx = (ur[0] - ll[0]) / max(nx, 1)
    dy = (ur[1] - ll[1]) / max(ny, 1)
    xs = ll[0] + (np.arange(nx) + 0.5) * dx
    ys = ll[1] + (np.arange(ny) + 0.5) * dy
    xx, yy = np.meshgrid(xs, ys, indexing="ij")
    radius = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    # Broadcast over z if needed.
    if nz > 1:
        radius = np.repeat(radius[:, :, np.newaxis], nz, axis=2)
    else:
        radius = radius[:, :, np.newaxis]
    r_max = float(radius.max()) if radius.size else 0.0
    outer_mask = radius >= (2.0 / 3.0) * r_max if r_max > 0 else np.zeros_like(spatial_any, dtype=bool)
    outer_total = int(outer_mask.sum())
    outer_hit = int(np.logical_and(outer_mask, spatial_any).sum()) if outer_total else 0
    outer_coverage = float(outer_hit / outer_total) if outer_total else 0.0

    # Lineout along +y through mesh centre (fuel mid ≈ world origin for app-slice).
    ix = nx // 2
    iz = 0
    line_lo = []
    line_r = []
    for iy in range(ny):
        cell_vals = lo[ix, iy, iz, :]
        cell_pos = cell_vals[np.isfinite(cell_vals) & (cell_vals > 0.0)]
        line_r.append(float(ys[iy] - cy))
        line_lo.append(float(cell_pos.max()) if cell_pos.size else 0.0)
    # How far along +y do we still have windows?
    reach_y = None
    for r_cm, w in zip(reversed(line_r), reversed(line_lo)):
        if w > 0.0:
            reach_y = float(r_cm)
            break

    return {
        "n_sets": n_sets,
        "spatial_coverage": spatial_coverage,
        "energy_coverage": energy_coverage,
        "lower_min": lo_min,
        "lower_max": lo_max,
        "decades": decades,
        "outer_coverage": outer_coverage,
        "outer_hit": outer_hit,
        "outer_total": outer_total,
        "reach_y_cm": reach_y,
        "mesh_r_max_cm": r_max,
        "voxels_hit": int(spatial_any.sum()),
        "voxels_total": int(spatial_any.size),
        "lineout_y_r_cm": line_r,
        "lineout_y_lower": line_lo,
    }


def print_weight_windows_depth_summary(stats: dict) -> None:
    """Human-readable shield-penetration summary for the Simulation log."""
    spat = 100.0 * float(stats.get("spatial_coverage") or 0.0)
    ener = 100.0 * float(stats.get("energy_coverage") or 0.0)
    outer = 100.0 * float(stats.get("outer_coverage") or 0.0)
    decades = stats.get("decades")
    lo_min = stats.get("lower_min")
    lo_max = stats.get("lower_max")
    reach = stats.get("reach_y_cm")
    r_max = stats.get("mesh_r_max_cm")
    hit = stats.get("voxels_hit")
    total = stats.get("voxels_total")

    print("-------- Weight-window depth --------")
    n_sets = stats.get("n_sets")
    if n_sets and int(n_sets) > 1:
        print(f"(using latest of {n_sets} WW sets in file)")
    print(
        f"Spatial coverage: {spat:.1f}% of voxels "
        f"({hit}/{total} with any energy window)"
    )
    print(f"Energy×voxel coverage: {ener:.1f}%")
    if decades is not None and lo_min is not None and lo_max is not None:
        print(
            f"Lower-bound span: {decades:.2f} decades "
            f"({lo_min:.3e} … {lo_max:.3e})"
        )
    else:
        print("Lower-bound span: n/a (no positive windows)")
    print(
        f"Outer-third coverage: {outer:.1f}% "
        f"({stats.get('outer_hit')}/{stats.get('outer_total')} voxels)"
    )
    if reach is not None and r_max:
        print(
            f"Farthest +y window: r≈{reach:.0f} cm "
            f"(mesh radial extent ≈{r_max:.0f} cm)"
        )
    # Compact radial profile: 6 bins from centre to +y edge.
    line_r = stats.get("lineout_y_r_cm") or []
    line_lo = stats.get("lineout_y_lower") or []
    pos = [(r, w) for r, w in zip(line_r, line_lo) if r >= 0.0]
    if pos:
        n_bins = min(6, len(pos))
        edges = np.linspace(0.0, pos[-1][0] if pos[-1][0] > 0 else 1.0, n_bins + 1)
        parts = []
        for i in range(n_bins):
            lo_r, hi_r = edges[i], edges[i + 1]
            chunk = [w for r, w in pos if (r >= lo_r and (r < hi_r or i == n_bins - 1))]
            if not chunk or max(chunk) <= 0.0:
                parts.append(f"{hi_r:.0f}cm:·")
            else:
                parts.append(f"{hi_r:.0f}cm:{max(chunk):.1e}")
        print("Lineout +y (max lower WW): " + " | ".join(parts))
    print(
        "Tip: low outer coverage / few decades → refine again; "
        "then run keff with weight_windows=use for DDD."
    )
    print("------------------------------------")


def write_ww_meta(
    *,
    pass_kind: str,
    mesh_cm: float,
    energy_groups: int,
    batches: int,
) -> None:
    """Record how weight_windows.h5 was produced (read by the Simulation tab)."""
    previous = 0
    path = Path(WW_META_FILE)
    if path.is_file():
        try:
            previous = int(json.loads(path.read_text(encoding="utf-8")).get("passes", 0))
        except (json.JSONDecodeError, TypeError, ValueError):
            previous = 0
    passes = previous + 1 if pass_kind == "refine" else 1
    payload = {
        "passes": passes,
        "last_pass": pass_kind,
        "mesh_cm": float(mesh_cm),
        "energy_groups": int(energy_groups),
        "batches": int(batches),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "file": WW_FILE,
    }
    try:
        depth = summarize_weight_windows(WW_FILE)
        payload["spatial_coverage"] = depth["spatial_coverage"]
        payload["energy_coverage"] = depth["energy_coverage"]
        payload["outer_coverage"] = depth["outer_coverage"]
        payload["decades"] = depth["decades"]
        payload["lower_min"] = depth["lower_min"]
        payload["lower_max"] = depth["lower_max"]
        payload["reach_y_cm"] = depth["reach_y_cm"]
        payload["mesh_r_max_cm"] = depth["mesh_r_max_cm"]
        print_weight_windows_depth_summary(depth)
        # Drop older MAGIC generations so the next refine/use loads only the latest.
        prune_weight_windows_file(WW_FILE)
    except Exception as exc:
        print(f"Weight-window depth summary skipped: {exc}")
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        f"Weight windows: {pass_kind} pass #{passes} → {WW_FILE} "
        f"(mesh {mesh_cm:g} cm, {energy_groups} energy groups)"
    )


def check_ww_mesh_is_inside_geometry(mesh, geometry):
    # App-slice vacuum planes leave OpenMC's auto bbox at ±inf in z.
    # Compare only finite coordinates against the mesh we built from bounding_box.
    ll_geom = np.asarray(geometry.bounding_box[0], dtype=float)
    ur_geom = np.asarray(geometry.bounding_box[1], dtype=float)
    mesh_ll = np.asarray(mesh.lower_left, dtype=float)
    mesh_ur = np.asarray(mesh.upper_right, dtype=float)
    finite = np.isfinite(ll_geom) & np.isfinite(ur_geom)
    if not np.any(finite):
        print("Weight-window mesh: geometry bbox is unbounded; using the run bounding box")
        return
    inside = bool(
        np.all(mesh_ll[finite] <= ll_geom[finite])
        and np.all(mesh_ur[finite] >= ur_geom[finite])
    )
    if inside:
        print("✅  mesh covers the finite geometry extents")
    else:
        print("❌  mesh misses part of the geometry")
        print("    geometry ll:", ll_geom, "  mesh ll:", mesh_ll)
        print("    geometry ur:", ur_geom, "  mesh ur:", mesh_ur)


def make_sim_settings(
    deterministic: bool = True,
    batches: int = 1500,
    weight_windows: WeightWindows = "no",
    lower_left_corner: tuple = (0, 0, 0),
    upper_right_corner: tuple = (0, 0, 0),
    geometry: openmc.Geometry = None,
    particle_type: Literal["neutron", "photon"] = "neutron",
    survival_biasing: bool = True,
    ww_mesh_cm: float = 10.0,
    ww_energy_groups: int = 10,
):
    # Define neutron source
    source = openmc.IndependentSource(space=openmc.stats.Point((0, 0, 0)))
    # Define simulation settings
    settings = openmc.Settings()
    settings.inactive = 10
    settings.max_history_splits = 5000  # cap long histories
    UPDATE_INTERVAL = 8
    settings.photon_transport = particle_type == "photon"
    settings.source = source
    building_ww = weight_windows in ("generate", "seed", "refine")
    # Periodic z-cones + WW particle splits (on-the-fly MAGIC or applied
    # windows) lose particles after boundary jumps in this geometry. Seed uses
    # offline MAGIC (tally then generate). Refine/use keep applied windows but
    # also keep offline generation so splits are only from the loaded windows.
    if building_ww:
        # MAGIC needs active batches after fission source convergence.
        ww_active = max(2 * UPDATE_INTERVAL, 16)
        settings.batches = settings.inactive + ww_active
        if int(batches) > settings.batches:
            settings.batches = int(batches)
        WEIGHT_WINDOWS_BATCHES = settings.batches
    else:
        WEIGHT_WINDOWS_BATCHES = max(8, int(batches / 10))
        settings.batches = batches
    print(
        f"batches {settings.batches} "
        f"(inactive {settings.inactive}, active {settings.batches - settings.inactive})"
    )

    settings.particles = 10000
    settings.generations_per_batch = 10
    settings.seed = 42
    settings.survival_biasing = survival_biasing
    if survival_biasing:
        settings.cutoff = {
            "weight": 0.25,                  # w_c: roulette threshold
            "weight_avg": 1.0,               # w_s: post-survival weight
            # If you want cutoffs relative to starting weight instead of current weight:
            # "survival_normalization": True
        }

    settings.rel_max_lost_particles = 0.01
    settings.confidence_intervals = True

    if 1 / (settings.particles * settings.generations_per_batch) >= 1 / (math.sqrt(settings.batches)):
        raise ValueError("The number of particles per generation per batch is too low to achieve the desired confidence interval. Increase the number of particles per generation per batch or increase the number of batches.")

    if not deterministic:
        settings.seed = int(time.time())

    if building_ww:
        # Seed/refine are for window shape, not final tallies: fewer histories
        # and a coarser mesh keep runtime hours → minutes.
        settings.particles = min(settings.particles, 2000)
        settings.rel_max_lost_particles = 0.05
        ww_mesh = make_ww_mesh(
            lower_left_corner, upper_right_corner, cell_dimension=ww_mesh_cm
        )
        check_ww_mesh_is_inside_geometry(ww_mesh, geometry)
        # on_the_fly=False: tally during analog/biased transport, write WW at
        # end. on_the_fly=True + periodic z-cones aborts with lost particles.
        wwg = openmc.WeightWindowGenerator(
            method="magic",
            mesh=ww_mesh,
            energy_bounds=ww_energy_bounds(ww_energy_groups),
            max_realizations=max(1, settings.batches - settings.inactive),
            update_interval=UPDATE_INTERVAL,
            on_the_fly=False,
        )
        settings.weight_window_generators = wwg
        if weight_windows == "refine":
            if not Path(WW_FILE).is_file():
                raise FileNotFoundError(
                    f"{WW_FILE} not found. Run a seed pass before refine."
                )
            # Apply the previous windows while MAGIC regenerates deeper ones.
            settings.weight_window_checkpoints = {
                "collision": True,
                "surface": False,
            }
            settings.weight_windows_on = True
            settings.weight_windows = [latest_weight_windows(WW_FILE)]
            settings.survival_biasing = False
            settings.cutoff = {"weight": 1e-4, "weight_avg": 1.0}
            # Cap splits: WW+periodic-cone secondary bank is fragile.
            settings.max_history_splits = min(settings.max_history_splits, 500)
            settings.rel_max_lost_particles = max(
                settings.rel_max_lost_particles, 0.05
            )
            # Default -1 writes an HDF5 dump per lost particle — kills refine runtime.
            # OpenMC's Python API requires > 0; 1 keeps a single diagnostic dump.
            settings.max_write_lost_particles = 1
            print(f"Weight windows: refining from latest set in {WW_FILE}")
        else:
            print("Weight windows: seeding MAGIC (offline, after analog transport)")
            settings.max_write_lost_particles = 1
        print(
            f"Weight windows: {settings.particles} particles/gen, "
            f"rel_max_lost={settings.rel_max_lost_particles}, on_the_fly=False"
        )
    elif weight_windows == "use":
        if not Path(WW_FILE).is_file():
            raise FileNotFoundError(
                f"{WW_FILE} not found. Seed (and refine) weight windows first."
            )
        settings.weight_window_checkpoints = {
            "collision": True,
            "surface": False,
        }
        settings.weight_windows_on = True
        settings.weight_windows = [latest_weight_windows(WW_FILE)]
        settings.survival_biasing = False  # WW handles weights
        settings.cutoff = {"weight": 1e-4, "weight_avg": 1.0}  # RR safety
        settings.max_history_splits = min(settings.max_history_splits, 500)
        # Applied WW splits on periodic z-cones can lose a few particles.
        settings.rel_max_lost_particles = max(settings.rel_max_lost_particles, 0.05)
        settings.max_write_lost_particles = 1

    return settings


def make_sim_photon_from_cells(
    source_cells: List[openmc.Cell],
    gamma_E_MeV: float = 1.27,  # MeV
    deterministic: bool = True,
    batches: int = 1500,
):
    settings = make_sim_settings(
        deterministic, batches, "no", (0, 0, 0), (0, 0, 0), None, "photon"
    )
    sources = []
    for c in source_cells:
        # Bounding box gives something to sample in; rejection via constraints keeps it inside
        ll, ur = c.bounding_box
        space_dist = openmc.stats.Box(ll, ur)  # uniform in the box
        energy_dist = openmc.stats.delta_function(gamma_E_MeV * 1e6)  # eV input
        angle_dist = openmc.stats.Isotropic()

        src = openmc.IndependentSource(
            particle="photon",
            space=space_dist,
            energy=energy_dist,
            angle=angle_dist,
            constraints={"domains": [c]},  # << keeps points inside cell
        )
        sources.append(src)
    settings.run_mode = "fixed source"
    settings.source = sources

    return settings


def run_keff_sim(
    geometry: openmc.Geometry,
    settings: openmc.Settings,
    materials_dict: Dict[str, openmc.Material],
    quiet: bool = True,
):
    print()
    mode = getattr(settings, "run_mode", None) or "eigenvalue"
    title = (
        "Fixed-source simulation"
        if str(mode).startswith("fixed")
        else "Criticality simulation"
    )
    print(f"-------- {title} --------")
    print()
    print("Seed :", settings.seed, "\n")
    run_sim(geometry, settings, materials_dict, quiet=quiet)


def render_geometry(
    universe,
    universe_radius,
    pixels,
    basis,
    origin,
    geometry,
    colors,
    materials_dict,
    universe_height=None,
):
    if universe_height is None:
        universe_height = universe_radius * 2
    materials = openmc.Materials(materials_dict.values())
    materials.export_to_xml()
    geometry.export_to_xml()
    print("Rendering geometry")
    plot = openmc.Plot()
    plot.width = [universe_radius * 2, universe_height]
    plot.pixels = pixels
    plot.basis = basis
    plot.color_by = "material"
    plot.colors = colors
    plot.origin = origin
    plot.show_overlaps = True
    plot.overlap_color = "red"
    image = plot.to_ipython_image()

    # Save the image to a local file
    with open("plot.png", "wb") as f:
        f.write(image.data)


def stochastic_volume_calculation(
    cells: List[openmc.Cell],
    geometry: openmc.Geometry,
    materials_dict: Dict[str, openmc.Material],
    geometry_settings: GeometrySettings = None,
    samples: int = 10000000,
    bounding_box=None,
):
    """
    Stochastic volume calculation, adds volume information to the cells
    """
    # Annulus sheets already carry an exact volume. Sampling them inside the
    # tilted-shell box misses thin gaps (a 0.05 cm absorber void is ~1e-5 of the box).
    pending = [cell for cell in cells if cell.volume is None]
    if pending:
        if bounding_box is not None:
            lower_left_corner, upper_right_corner = bounding_box
        else:
            lower_left_corner, upper_right_corner = get_geometry_bounding_box(
                geometry_settings
            )
        # 1e5 samples per cell is usually enough for <1 % error
        volcalc = openmc.VolumeCalculation(
            domains=pending,
            samples=samples,
            lower_left=lower_left_corner,
            upper_right=upper_right_corner,
        )
        settings = openmc.Settings()
        settings.volume_calculations = [volcalc]
        settings.run_mode = "volume"
        settings.export_to_xml()
        run_sim(geometry, settings, materials_dict, quiet=True)

        # Read uncertainty directly from HDF5 file
        all_ok = True
        with h5py.File("volume_1.h5", "r") as f:
            for cell in pending:
                cell_id = cell.id
                vol_data = f[f"domain_{cell_id}/volume"][:]
                volume = vol_data[0]
                std_dev = vol_data[1]
                rel_uncertainty = std_dev / volume * 100 if volume > 0 else float("inf")
                # Universe fills (boundary_layer / column parents) are not used for mass;
                # their regions can be thin wedges of a large sample box.
                fill = cell.fill
                is_universe_fill = fill is not None and not isinstance(
                    fill, openmc.Material
                )
                if (
                    rel_uncertainty == float("inf")
                    or "boundary_layer" in (cell.name or "")
                    or is_universe_fill
                ):
                    cell.volume = 0.0
                    continue
                if rel_uncertainty > 5.0:
                    all_ok = False
                    raise ValueError(
                        f"❌ Volume calculation uncertainty too high ({rel_uncertainty:.1f}%) for cell '{cell.name}' (ID {cell_id}).\n"
                        f"    Increase number of samples or check geometry."
                    )
        if all_ok:
            print("✅ All volume calculation uncertainties are below 5%.")

        vol_calc = openmc.VolumeCalculation.from_hdf5("volume_1.h5")
        geometry.add_volume_information(vol_calc)  # attaches .volume to each cell
    return geometry


def compute_burnup(
    thermal_power: float,  # W
    time_table: List[float],  # d
    fuel_mass: float,  # kg
) -> List[float]:
    burnup = []
    for time in time_table:
        burnup.append(thermal_power / 1e6 * time / fuel_mass)
    return burnup


def print_depletion_result(materials_dict, material_choice, thermal_power, fuel_mass):
    results = openmc.deplete.Results("depletion_results.h5")
    time, keff = results.get_keff(time_units="d")
    uranium_burnups = compute_burnup(thermal_power, time, fuel_mass)
    results.export_to_materials(burnup_index=1)
    hm_results_table = [
        ["Time (year)"] + [round(t / 365, 3) for t in time],
        ["Keff"] + [round(a[0], 3) for a in keff],
        ["Uranium Burnup (MWd/kgHM)"] + [round(a, 3) for a in uranium_burnups],
        ["U232 (mol)"]
        + [
            round(a / cst.Avogadro, 3)
            for a in results.get_atoms(
                mat=materials_dict[material_choice.fuel], nuc="U232", time_units="d"
            )[1]
        ],
        ["U233 (mol)"]
        + [
            round(a / cst.Avogadro, 3)
            for a in results.get_atoms(
                mat=materials_dict[material_choice.fuel], nuc="U233", time_units="d"
            )[1]
        ],
        ["U234 (mol)"]
        + [
            round(a / cst.Avogadro, 3)
            for a in results.get_atoms(
                mat=materials_dict[material_choice.fuel], nuc="U234", time_units="d"
            )[1]
        ],
        ["U235 (mol)"]
        + [
            round(a / cst.Avogadro, 3)
            for a in results.get_atoms(
                mat=materials_dict[material_choice.fuel], nuc="U235", time_units="d"
            )[1]
        ],
        ["U236 (mol)"]
        + [
            round(a / cst.Avogadro, 3)
            for a in results.get_atoms(
                mat=materials_dict[material_choice.fuel], nuc="U236", time_units="d"
            )[1]
        ],
        ["Np237 (mol)"]
        + [
            round(a / cst.Avogadro, 5)
            for a in results.get_atoms(
                mat=materials_dict[material_choice.fuel], nuc="Np237", time_units="d"
            )[1]
        ],
        ["Pu238 (mol)"]
        + [
            round(a / cst.Avogadro, 5)
            for a in results.get_atoms(
                mat=materials_dict[material_choice.fuel], nuc="Pu238", time_units="d"
            )[1]
        ],
        ["U238 (mol)"]
        + [
            round(a / cst.Avogadro, 3)
            for a in results.get_atoms(
                mat=materials_dict[material_choice.fuel], nuc="U238", time_units="d"
            )[1]
        ],
        ["Pu239 (mol)"]
        + [
            round(a / cst.Avogadro, 5)
            for a in results.get_atoms(
                mat=materials_dict[material_choice.fuel], nuc="Pu239", time_units="d"
            )[1]
        ],
        ["Pu240 (mol)"]
        + [
            round(a / cst.Avogadro, 5)
            for a in results.get_atoms(
                mat=materials_dict[material_choice.fuel], nuc="Pu240", time_units="d"
            )[1]
        ],
        ["Pu241 (mol)"]
        + [
            round(a / cst.Avogadro, 5)
            for a in results.get_atoms(
                mat=materials_dict[material_choice.fuel], nuc="Pu241", time_units="d"
            )[1]
        ],
        ["Pu242 (mol)"]
        + [
            round(a / cst.Avogadro, 5)
            for a in results.get_atoms(
                mat=materials_dict[material_choice.fuel], nuc="Pu242", time_units="d"
            )[1]
        ],
    ]
    fission_products_results_table = [
        ["Time (year)"] + [round(t / 365, 3) for t in time],
        ["Keff"] + [round(a[0], 3) for a in keff],
        ["Uranium Burnup (MWd/kgHM)"] + [round(a, 3) for a in uranium_burnups],
        ["Xe135 (mol)"]
        + [
            round(a / cst.Avogadro, 5)
            for a in results.get_atoms(
                mat=materials_dict[material_choice.fuel], nuc="Xe135", time_units="d"
            )[1]
        ],
        ["Sm149 (mol)"]
        + [
            round(a / cst.Avogadro, 5)
            for a in results.get_atoms(
                mat=materials_dict[material_choice.fuel], nuc="Sm149", time_units="d"
            )[1]
        ],
        ["Gd157 (mol)"]
        + [
            round(a / cst.Avogadro, 5)
            for a in results.get_atoms(
                mat=materials_dict[material_choice.fuel], nuc="Gd157", time_units="d"
            )[1]
        ],
    ]
    print("Heavy metals")
    print(tabulate(hm_results_table))
    print("Notable fission products")
    print(tabulate(fission_products_results_table))


def run_depletion_sim(
    thermal_power: float,
    geometry,
    settings,
    materials,
    sim_steps: List[float] = [],
    steps_units: str = "d",
):
    fission_q = {"U235": 202.5e6}  # energy in eV # "U233": 200.1e6, "Pu239": 211.5e6
    model = openmc.Model(geometry, materials, settings)
    op = openmc.deplete.CoupledOperator(
        model, "chain_endfb71_pwr.xml", fission_q=fission_q
    )
    max_step = 2 * op.heavy_metal / thermal_power * 1e3
    # Check if any timestep exceeds the maximum allowed step size
    for step in sim_steps:
        if step > max_step:
            print(
                f"Timestep {step} {steps_units} exceeds maximum allowed step size of {max_step:.2f} {steps_units}. "
                f"This limit is based on the heavy metal content and thermal power."
            )

    openmc.deplete.CECMIntegrator(
        op, sim_steps, thermal_power, timestep_units=steps_units
    ).integrate()


def calculate_source_strength(
    power_output_watts,
):
    # Calculate neutrons per second based on power output
    # Average energy released per fission: ~200 MeV = 3.2e-11 Joules
    energy_per_fission = 200 * 1.6e-13  # Joules
    neutrons_per_fission = 2.4  # Average number of neutrons per fission

    # Calculate fissions per second based on power
    fissions_per_second = power_output_watts / energy_per_fission

    # Calculate source strength (neutrons/second)
    source_strength = fissions_per_second * neutrons_per_fission

    return source_strength


def run_sim_with_tallies(
    geometry: openmc.Geometry,
    settings: openmc.Settings,
    materials_dict: Dict[str, openmc.Material],
    photovoltaic_cells: List[openmc.Cell],
    photovoltaic_density: float,
    emitter_cells: List[openmc.Cell],
    fuel_cells: List[openmc.Cell],
    moderator_cells: List[openmc.Cell],
    shield_moderator_cells: List[openmc.Cell],
    coolant_cells: List[openmc.Cell],
    electric_power: float,
    heat_deposition_cells: List[openmc.Cell],
    source_strength: float,
    batches: int,
    dose_time: float,
    particle_type: Literal["neutron", "photon"] = "neutron",
    monitored_nuclide: MonitoredNuclide = None,
    ddd_tallies_only: bool = False,
):
    photovoltaic_flux_tally = create_photovoltaic_flux_tally(
        photovoltaic_cells, particle_type
    )

    if ddd_tallies_only:
        print("Tallies: photovoltaic DDD only (SR-NIEL flux on InGaAs cells).")
        tallies = openmc.Tallies([photovoltaic_flux_tally])
    else:
        tally_photovoltaic = create_photovoltaic_heating_absorption_tally(
            photovoltaic_cells, particle_type, monitored_nuclide
        )
        tally_tritium_production_moderator = create_tritium_production_tally(
            moderator_cells, suffix="_moderator"
        )
        tally_tritium_production_shield = create_tritium_production_tally(
            shield_moderator_cells, suffix="_shield_moderator"
        )
        tally_tritium_production_coolant = create_tritium_production_tally(
            coolant_cells, suffix="_coolant"
        )
        tally_C14_production_moderator = create_C14_production_tally(
            moderator_cells, suffix="_moderator"
        )
        tally_C14_production_shield = create_C14_production_tally(
            shield_moderator_cells, suffix="_shield_moderator"
        )
        tally_C14_production_coolant = create_C14_production_tally(
            coolant_cells, suffix="_coolant"
        )
        tally_O16_activation_moderator = create_O16_activation_tally(
            moderator_cells, suffix="_moderator"
        )
        tally_O16_activation_shield = create_O16_activation_tally(
            shield_moderator_cells, suffix="_shield_moderator"
        )
        tally_O16_activation_coolant = create_O16_activation_tally(
            coolant_cells, suffix="_coolant"
        )
        t_flux, t_nufi, t_Enufi = create_fission_energy_weighted_flux_tally(fuel_cells)
        tally_emitter = create_emitter_tally(
            emitter_cells, materials_dict, particle_type, monitored_nuclide
        )
        tally_photovoltaic_flux_band = create_flux_band_tally(
            photovoltaic_cells, "phi_E_photovoltaic"
        )
        t_heat_cells, t_heat_total, t_kapf_total = create_energy_deposition_tallies(
            heat_deposition_cells, use_heating_local=particle_type != "photon"
        )
        dpa_emitter = create_dpa_tally(emitter_cells, suffix="_emitter")
        t_heat_moderator_cells, t_heat_moderator_total, t_kapf_moderator_total = (
            create_energy_deposition_tallies(
                moderator_cells,
                use_heating_local=particle_type != "photon",
                tally_prefix="dep_moderator_",
            )
        )
        # IFP tally: no filters -> global; three scores in one tally
        tally_ifp = openmc.Tally(name="ifp-scores")
        tally_ifp.scores = ["ifp-time-numerator", "ifp-beta-numerator", "ifp-denominator"]

        tallies = openmc.Tallies(
            [
                tally_photovoltaic,
                photovoltaic_flux_tally,
                tally_emitter,
                tally_ifp,
                t_flux,
                t_nufi,
                t_Enufi,
                tally_photovoltaic_flux_band,
                t_heat_cells,
                t_heat_total,
                t_kapf_total,
                t_heat_moderator_cells,
                t_heat_moderator_total,
                t_kapf_moderator_total,
                tally_tritium_production_moderator,
                tally_tritium_production_shield,
                tally_tritium_production_coolant,
                tally_C14_production_moderator,
                tally_C14_production_shield,
                tally_C14_production_coolant,
                tally_O16_activation_moderator,
                tally_O16_activation_shield,
                tally_O16_activation_coolant,
                dpa_emitter,
            ]
        )
    run_sim(geometry, settings, materials_dict, tallies, quiet=True)
    print_tallies(
        source_strength,
        emitter_cells,
        sum(cell.volume for cell in photovoltaic_cells),
        photovoltaic_density,
        sum(cell.volume for cell in emitter_cells),
        electric_power,
        batches,
        dose_time,
        ddd_tallies_only=ddd_tallies_only,
    )

    # clean_directory()


def xe135_peak_mass_g(
    P_th_W,
    # --- defaults (SI) ---
    thermal_flux=3.7e17,  # n·m^-2·s^-1  (≈3.7e13 n·cm^-2·s^-1 typical PWR)
    E_f_J=200e6 * 1.602176634e-19,  # J per fission (~200 MeV)
    y_I=6.28968e-2,  # I-135 cumulative yield per fission (U-235, thermal)
    t12_I_s=6.57 * 3600.0,  # I-135 half-life (s)
    t12_Xe_s=9.14 * 3600.0,  # Xe-135 half-life (s)
    M_Xe135_kg_per_mol=134.9072075e-3,  # kg·mol^-1
    N_A=6.02214076e23,  # mol^-1
):
    """
    Return the total mass (kg) of Xe-135 in the core at its post-shutdown maximum,
    assuming long full-power operation (I-135 at equilibrium) followed by shutdown.
    Inputs are SI; P_th_W is thermal power in watts.
    """

    # decay constants
    lam_I = math.log(2) / t12_I_s
    lam_Xe = math.log(2) / t12_Xe_s

    # fission rate (#/s)
    F = P_th_W / E_f_J

    # Xe-135 absorption removal rate during full power, r=0.02 is the epithermal index
    sigma_a_xe135 = 2.65e-22
    sigmaPhi = thermal_flux * sigma_a_xe135

    # Equilibrium inventories at power:
    # I0 = y_I * F / lam_I ; Xe0 not needed explicitly for the peak formula below
    I0 = y_I * F / lam_I

    # Time-to-peak after shutdown (Φ → 0) for the long-run steady state:
    # t_peak = ln[ (lam_Xe/lam_I)*((lam_I+sigmaPhi)/(lam_Xe+sigmaPhi)) ] / (lam_Xe - lam_I)
    bracket = (lam_Xe / lam_I) * ((lam_I + sigmaPhi) / (lam_Xe + sigmaPhi))
    t_peak = math.log(bracket) / (lam_Xe - lam_I)

    # At the peak, Xe = (lam_I/lam_Xe)*I(t_peak)
    I_tp = I0 * math.exp(-lam_I * t_peak)
    N_Xe_peak = (lam_I / lam_Xe) * I_tp  # atoms

    # convert atoms -> mass (g)
    m_g = (N_Xe_peak / N_A) * M_Xe135_kg_per_mol * 1e3
    return m_g


def add_xe135_to_geometry(
    geometry, materials_dict, material_choice, core_characteristics
):
    # For all cells in the geometry that have the same material as material_choice.fuel,
    # print their volume and change their composition to add 5% Xenon135 by weight

    # Find the material object for the fuel
    fuel_material = materials_dict[material_choice.fuel]

    # Get all cells in the geometry
    all_cells = [cell for _, cell in geometry.get_all_cells().items()]

    found_cells = []

    # Loop through all cells and find those with the same material as the fuel
    for cell in all_cells:
        # cell.fill can be a Material or a Universe; we want only Material
        if hasattr(cell, "fill") and isinstance(cell.fill, type(fuel_material)):
            if cell.fill is fuel_material:
                xe135 = openmc.Material(name="Xe135")
                xe135.add_nuclide("Xe135", 1.0, "wo")
                xe135.set_density("g/cm3", 12)
                weight_xe135 = xe135_peak_mass_g(core_characteristics.core_power)
                weight_fuel = cell.volume * fuel_material.density
                weight_total = weight_fuel + weight_xe135
                weight_xe135_fraction = weight_xe135 / weight_total
                new_material = openmc.Material.mix_materials(
                    [fuel_material, xe135],
                    [1 - weight_xe135_fraction, weight_xe135_fraction],
                    "wo",
                )
                new_material.name = "Fuel + Xe135"
                materials_dict[new_material.name] = new_material
                cell.fill = new_material
                found_cells.append(cell)
    if len(found_cells) > 1:
        raise ValueError("Found multiple cells with the same fuel material")


def print_core_characteristics(
    core_characteristics: CoreCharacteristics,
):
    print(
        "rotary axle diameter",
        round(core_characteristics.rotary_axle_radius * 2),
        "cm",
    )
    print(
        "vertical core height",
        round(core_characteristics.vertical_core_height, 2),
        "cm",
    )
    print(
        "cold temp",
        round(core_characteristics.cold_temp - 273),
        "°C",
    )
    print(
        "emissive_surface",
        round(core_characteristics.fuel_emissive_area / 1e4, 2),
        "m2",
    )
    print(
        "Radiative flux",
        round(
            core_characteristics.radiative_flux,
        ),
        "W/m2",
    )
    print("core power", round(core_characteristics.core_power / 1e6, 2), "MW")
    print(
        "core power electric",
        round(core_characteristics.core_power_electric / 1e6, 2),
        "MW",
    )
    print(
        "photovoltaic power",
        round(core_characteristics.photovoltaic_power / 1e6, 2),
        "MW",
    )

    print(
        "photovoltaic power density",
        round(core_characteristics.photovoltaic_power_density * 1e4, 2),
        "W/m2",
    )
    print(
        "photovoltaic power per m",
        round(core_characteristics.photovoltaic_power_per_m / 1e6, 2),
        "MW/m",
    )

    print(
        "photovoltaic area",
        round(core_characteristics.photovoltaic_area / 1e4, 2),
        "m2",
    )

    print("fuel lifetime", core_characteristics.fuel_lifetime, "years")
    print("fuel thickness", round(core_characteristics.fuel_thickness*10, 2), "mm")
