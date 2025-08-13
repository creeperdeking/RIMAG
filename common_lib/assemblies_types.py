from typing import List, Optional, Literal
from pydantic import BaseModel

from common_lib.rotary_assembly import RotaryAssemblyDesc


class CoreDesc(BaseModel):
    core_radius: float
    core_height: float
    outer_core_radius: float


class Assembly(BaseModel):
    thickness: float
    material: Optional[str] = None
    is_fuel: bool = False
    is_emitter: Optional[bool] = False
    is_emitter_placeholder: Optional[bool] = False
    is_photovoltaic: Optional[bool] = False


class EmitterPlaceholder(Assembly):
    thickness: float
    is_emitter: Literal[True] = True


class AssemblySections(BaseModel):
    parts: List[Assembly | EmitterPlaceholder]


class OuterCoreAssemblySections(AssemblySections):
    layer_thickness: float


class BoundariesGeometrySettings:
    emitter_assembly: AssemblySections
    rotary_assembly_desc: RotaryAssemblyDesc
    core_desc: CoreDesc
    double_assembly: bool
