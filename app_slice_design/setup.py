"""Load and validate the JSON payload written by the reactor-slice web app."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Literal

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
    stack_m: float
    columns: float
    fuel_temp_c: float = 1150.0
    reload_fraction: Literal["1/2", "1/3", "1/4", "1/5"] = "1/4"
    dims: bool = True
    layers: Dict[str, List[LayerRow]]

    model_config = {"populate_by_name": True}


class AppSliceSimulationParams(BaseModel):
    run_mode: Literal[
        "keff",
        "keff_notallies",
        "render",
        "depletion",
        "keff_emitter_gamma_source",
        "norun",
    ] = "render"
    n_batches: int = 200
    nsm_material: str = "Graphite"
    nsm_thickness: float = 25.0
    conical_pitch: float = 15.0
    particle_type: Literal["neutron", "photon"] = "neutron"
    weight_windows: Literal["no", "use", "generate"] = "no"
    dose_time: float = 10.0
    print_core_characteristics: bool = True


class AppSliceRunConfig(BaseModel):
    setup: AppSliceSetup
    simulation: AppSliceSimulationParams = Field(default_factory=AppSliceSimulationParams)


def load_app_slice_run_config(path: str | Path) -> AppSliceRunConfig:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return AppSliceRunConfig.model_validate(data)
