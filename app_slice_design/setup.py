"""Load and validate the JSON payload written by the reactor-slice web app."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class LayerRow(BaseModel):
    name: str
    cm: float


class AppSliceSetup(BaseModel):
    a: float
    absorber: float = Field(alias="abs")
    refl: float
    b_pct: float
    w: float
    ratio_pct: float
    tpv_density: float
    enrichment_pct: float
    packing_pct: float
    hm_particle_pct: float
    cylinder_diameter_mm: float
    wall_margin_mm: float
    compact_spacing_mm: float
    tpv_eff_pct: float
    # Thermodynamics-tab outputs for one transport period (every column, both
    # faces). The run uses these and does not solve its own temperature or flux.
    shell_temp_c: Optional[float] = None
    period_thermal_w: Optional[float] = Field(default=None, ge=0)
    period_electric_w: Optional[float] = Field(default=None, ge=0)
    tpv_absorbed_w_per_cm2: float = 0.0
    stack_m: float
    columns: float
    fuel_temp_c: float = 1150.0
    reload_fraction: Literal["1/2", "1/3", "1/4", "1/5"] = "1/4"
    dims: bool = True
    layers: Dict[str, List[LayerRow]]

    model_config = {"populate_by_name": True}


class SlabLayerSpec(BaseModel):
    name: str
    cm: float = Field(gt=0)
    role: Literal["reflector", "moderator", "absorber", "detector"]


class AppSliceSimulationParams(BaseModel):
    run_mode: Literal[
        "keff",
        "keff_notallies",
        "render",
        "depletion",
        "keff_emitter_gamma_source",
        "keff_gamma_dose",
        "norun",
        "slab",
    ] = "keff"
    n_batches: int = 200
    n_threads: int = 10
    nsm_material: str = "Graphite"
    nsm_thickness: float = 25.0
    conical_pitch: float = 15.0
    particle_type: Literal["neutron", "photon"] = "neutron"
    weight_windows: Literal["no", "use", "generate", "seed", "refine"] = "no"
    survival_biasing: bool = False
    dose_time: float = 10.0
    print_core_characteristics: bool = True
    boron_concentration_ppm: float = Field(default=0.0, ge=0)
    # When true, keff tallies are only the photovoltaic SR-NIEL DDD flux tally.
    ddd_tallies_only: bool = True
    # MAGIC weight-window mesh / groups for seed and refine passes.
    ww_mesh_cm: float = Field(default=40.0, gt=0)
    ww_energy_groups: int = Field(default=10, ge=1, le=200)
    # Whole-stack thermal power [MW]. When set, the modeled period uses its
    # height share of this value instead of the thermodynamics-tab period heat,
    # so two geometries can be compared at the same stack power. Absent or
    # non-positive means the tab's period heat.
    thermal_power_mw: Optional[float] = None
    # Fixed-source slab. The layers are the chord drawn in the Fast simulation
    # dialog, fuel side first. The runner adds the void score itself.
    slab_particles: int = Field(default=8000, ge=1, le=1_000_000)
    slab_layers: List[SlabLayerSpec] = Field(default_factory=list)


class AppSliceRunConfig(BaseModel):
    setup: AppSliceSetup
    simulation: AppSliceSimulationParams = Field(default_factory=AppSliceSimulationParams)


def load_app_slice_run_config(path: str | Path) -> AppSliceRunConfig:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return AppSliceRunConfig.model_validate(data)
