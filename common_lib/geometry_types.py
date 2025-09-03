from typing import List
from pydantic import BaseModel

from common_lib.assemblies_types import (
    AssemblySections,
    OuterCoreAssemblySections,
    CoreDesc,
)
from common_lib.materials import MaterialChoice
from common_lib.rotary_assembly import RotaryAssemblyDesc


class GeometrySettings(BaseModel):
    core_desc: CoreDesc
    rotary_assembly_desc: RotaryAssemblyDesc
    material_choice: MaterialChoice
    assembly_section_core: AssemblySections
    outer_core_layers_inside_shaft: AssemblySections
    outer_core_thickness: float
    outer_core_layers_between_disks: List[OuterCoreAssemblySections]
    outer_core_layers_bottom: AssemblySections
    double_assembly: bool = False
    emitter_assembly: AssemblySections
    photovoltaic_assembly: AssemblySections
