"""Fixed-source slab of the fuel-to-cell chord.

The web preview sends the layer list, so the thicknesses OpenMC runs are the
ones drawn in the Fast simulation dialog. Neutrons start at the fuel side,
aimed straight through the stack. The transverse faces are reflective, which
makes the slab infinite sideways. The score is the GaAs NIEL-weighted flux
in 1 cm of void after the absorber: the same weighting as the InGaAs DDD
tally, per source neutron.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import openmc

# NIEL(E) from scripts/srniel_GaAs_E722-19_compact.txt. E in MeV, NIEL in MeV cm2/g.
_NIEL_E_MEV = np.array(
    [
        1.025000e-10, 2.511929e-10, 6.155888e-10, 1.508600e-09, 3.697069e-09,
        9.060266e-09, 2.220365e-08, 5.441364e-08, 1.333494e-07, 3.267944e-07,
        8.008626e-07, 1.962644e-06, 4.809776e-06, 1.178714e-05, 2.888628e-05,
        7.079052e-05, 1.734836e-04, 4.251497e-04, 1.041898e-03, 2.553341e-03,
        6.257375e-03, 1.533471e-02, 3.758019e-02, 9.209635e-02, 2.256970e-01,
        5.531071e-01, 1.355479e00, 3.321820e00, 8.140658e00, 1.995000e01,
    ]
)
_NIEL = np.array(
    [
        1.028800e-04, 6.901627e-05, 4.664224e-05, 3.244308e-05, 2.308721e-05,
        1.674733e-05, 1.265294e-05, 9.965776e-06, 7.972622e-06, 6.666362e-06,
        5.554222e-06, 4.903378e-06, 4.210980e-06, 3.763132e-06, 3.422926e-06,
        3.762402e-06, 3.769742e-06, 6.157768e-06, 5.632171e-06, 1.956602e-05,
        4.518642e-05, 4.849501e-05, 8.942563e-05, 1.884219e-04, 3.327518e-04,
        4.787440e-04, 5.767292e-04, 7.201121e-04, 1.052412e-03, 1.142100e-03,
    ]
)


def _niel(energy_ev: float) -> float:
    energy_mev = max(energy_ev * 1e-6, float(_NIEL_E_MEV[0]))
    return float(np.interp(math.log(energy_mev), np.log(_NIEL_E_MEV), _NIEL))


def run_slab_shield(materials: dict, layers: list, particles: int, batches: int, threads: int) -> None:
    solids = [layer for layer in layers if getattr(layer, "role", "") != "detector"]
    if not solids:
        raise SystemExit(
            "Fast slab has no shield thickness. Queue it from the Fast simulation button."
        )

    print("Fast slab cross-section (fuel side → score):", flush=True)
    for layer in solids:
        print(f"  {float(layer.cm):.4g} cm  {layer.name}", flush=True)
    print("  1 cm  void score", flush=True)

    x = 0.0
    planes = [openmc.XPlane(0.0, boundary_type="vacuum")]
    fills: list[openmc.Material | None] = []
    used: list[openmc.Material] = []
    seen: set[int] = set()
    for layer in solids:
        x += float(layer.cm)
        planes.append(openmc.XPlane(x))
        name = str(layer.name).strip()
        if name.lower() == "void":
            fills.append(None)
            continue
        material = materials.get(name)
        if material is None:
            raise SystemExit(f"Fast slab has no OpenMC material named {name!r}.")
        fills.append(material)
        if id(material) not in seen:
            seen.add(id(material))
            used.append(material)
    score_x = x
    length = x + 1.0
    planes.append(openmc.XPlane(length, boundary_type="vacuum"))

    y0 = openmc.YPlane(-0.5, boundary_type="reflective")
    y1 = openmc.YPlane(0.5, boundary_type="reflective")
    z0 = openmc.ZPlane(-0.5, boundary_type="reflective")
    z1 = openmc.ZPlane(0.5, boundary_type="reflective")
    box = +y0 & -y1 & +z0 & -z1

    cells = []
    for index, material in enumerate(fills):
        cells.append(
            openmc.Cell(
                name=f"slab_{index}_{solids[index].role}",
                fill=material,
                region=+planes[index] & -planes[index + 1] & box,
            )
        )
    cells.append(
        openmc.Cell(
            name="slab_score",
            fill=None,
            region=+planes[-2] & -planes[-1] & box,
        )
    )

    model = openmc.Model()
    model.geometry = openmc.Geometry(cells)
    model.materials = openmc.Materials(used)

    edges = np.logspace(-5, math.log10(2e7), 41)
    mesh = openmc.RegularMesh()
    mesh.dimension = [1, 1, 1]
    mesh.lower_left = [score_x, -0.5, -0.5]
    mesh.upper_right = [length, 0.5, 0.5]
    tally = openmc.Tally(name="slab_score_flux")
    tally.filters = [openmc.MeshFilter(mesh), openmc.EnergyFilter(edges)]
    tally.scores = ["flux"]
    model.tallies = openmc.Tallies([tally])

    model.settings = openmc.Settings()
    model.settings.run_mode = "fixed source"
    model.settings.particles = max(1, int(particles))
    model.settings.batches = max(1, int(batches))
    model.settings.survival_biasing = False
    source_x = min(0.05, 0.5 * float(solids[0].cm))
    source = openmc.IndependentSource()
    source.space = openmc.stats.Point((source_x, 0.0, 0.0))
    source.angle = openmc.stats.Monodirectional((1.0, 0.0, 0.0))
    source.energy = openmc.stats.Watt(a=0.988e6, b=2.249e-6)
    model.settings.source = source

    # MAGIC windows on a 20 cm mesh. Written under slab_fast/ so the reactor
    # weight_windows.h5 in the run directory is left alone.
    n_ww = max(1, int(math.ceil(score_x / 20.0)))
    ww_mesh = openmc.RegularMesh()
    ww_mesh.dimension = [n_ww, 1, 1]
    ww_mesh.lower_left = [0.0, -0.5, -0.5]
    ww_mesh.upper_right = [length, 0.5, 0.5]
    model.settings.weight_window_generators = [
        openmc.WeightWindowGenerator(
            ww_mesh,
            energy_bounds=np.logspace(-5, math.log10(2e7), 9),
            method="magic",
            max_realizations=max(1, int(batches)),
            update_interval=1,
            on_the_fly=True,
        )
    ]

    out = Path("slab_fast")
    out.mkdir(parents=True, exist_ok=True)
    statepoint = model.run(threads=max(1, int(threads)), cwd=out)
    with openmc.StatePoint(statepoint) as sp:
        result = sp.get_tally(name="slab_score_flux")
        flux = result.get_values(scores=["flux"], value="mean").ravel()
        err = result.get_values(scores=["flux"], value="std_dev").ravel()

    mids = np.sqrt(edges[:-1] * edges[1:])
    niel_w = np.array([_niel(float(energy)) for energy in mids])
    weighted = flux * niel_w
    total = float(weighted.sum())
    print(f"Slab shield NIEL flux: {total:.4e}", flush=True)
    bands = [
        (1e-5, 0.5, "thermal <0.5 eV"),
        (0.5, 1e5, "epithermal"),
        (1e5, 2e7, "fast >100 keV"),
    ]
    for lo, hi, label in bands:
        mask = (mids >= lo) & (mids < hi)
        part = float(weighted[mask].sum())
        share = part / total if total > 0 else float("nan")
        print(f"  {label}: {part:.4e} ({100 * share:.1f}%)", flush=True)
    if total > 0:
        for index in np.argsort(weighted)[-5:]:
            rel = err[index] / flux[index] if flux[index] > 0 else float("nan")
            print(
                f"  group {mids[index]:.3e} eV  contribution {weighted[index] / total:.1%}  "
                f"flux rel {rel:.0%}",
                flush=True,
            )
