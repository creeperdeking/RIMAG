from pydantic import BaseModel


class RotaryAssemblyDesc(BaseModel):
    assembly_core_distance: float
    assembly_core_margin: float


class RotaryAssemblyLayer(BaseModel):

    radius: float
    """
    The radius of the layer
    """

    number: int
    """
    The number of the layer
    """
