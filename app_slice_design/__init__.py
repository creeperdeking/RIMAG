"""Build OpenMC geometry from an app_reactor_slice calculator setup."""

from app_slice_design.layout import ZoneLayout, compute_layout_for_ratio
from app_slice_design.setup import AppSliceRunConfig, load_app_slice_run_config

__all__ = [
    "AppSliceRunConfig",
    "ZoneLayout",
    "compute_layout_for_ratio",
    "load_app_slice_run_config",
]


def __getattr__(name: str):
    if name in {"MakeAppSliceGeometryResult", "make_app_slice_geometry"}:
        from app_slice_design.geometry import (
            MakeAppSliceGeometryResult,
            make_app_slice_geometry,
        )

        return {
            "MakeAppSliceGeometryResult": MakeAppSliceGeometryResult,
            "make_app_slice_geometry": make_app_slice_geometry,
        }[name]
    raise AttributeError(name)
