from common_lib.core import CoreDesc
from common_lib.rotary_assembly import RotaryAssemblyDesc

from common_lib.geometry_utils import AssemblySections
from pydantic import BaseModel
from common_lib.materials import MaterialChoice


class GeometrySettings(BaseModel):
    core_desc: CoreDesc
    rotary_assembly_desc: RotaryAssemblyDesc
    material_choice: MaterialChoice
    assembly_section_core: AssemblySections
    outer_core_layers: AssemblySections
    double_assembly: bool = False
    emitter_assembly: AssemblySections
