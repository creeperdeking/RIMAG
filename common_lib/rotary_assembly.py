from pydantic import BaseModel


class RotaryAssemblyDesc(BaseModel):
    assembly_core_distance: float
    assembly_core_margin: float
    rotary_assembly_radius: float
    angle: float = 45
