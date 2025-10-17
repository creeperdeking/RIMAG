from pydantic import BaseModel
from typing import Literal


class RotaryAssemblyDesc(BaseModel):
    assembly_core_distance: float
    rotary_assembly_radius: float
    frustum_pitch: float
    rotary_axle_thickness: float
    number_of_reactor_columns: Literal[1, 2, 3]
