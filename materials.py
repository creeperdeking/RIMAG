from typing import List, Optional


class Atom:
    name: str


class Material:
    name: str
    composition: List[Atom]
    density: float  # g/cm3
    specific_heat: Optional[float] = None  # J/g/K
    thermal_conductivity: Optional[float] = None  # W/cm/K
    melting_point: Optional[float] = None  # K
    boiling_point: Optional[float] = None  # K


materials: List[Material] = [
    {
        "name": "Uranium",
        "composition": [Atom(name="U-235")],
        "density": 18.95,
        "specific_heat": 0.032,
        "thermal_conductivity": 0.027,
        "melting_point": 1408,
        "boiling_point": 4131,
    }
]
