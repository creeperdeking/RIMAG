import pytest
import math

from common_lib.core import compute_core_desc
from common_lib.geometry_utils import AssemblySections
from common_lib.rotary_assembly import RotaryAssemblyDesc, RotaryAssemblyLayer
from drums import calculate_drum_surface_in_core


def test_drum_surface_in_core_zero_when_intersection_is_zero():
    drum_desc = RotaryAssemblyDesc(
        assembly_core_distance=10,
        assembly_core_margin=0,
    )
    core_desc = compute_core_desc(
        core_radius=5,
        core_height=1,
        outer_core_assembly=AssemblySections(parts=[]),
    )
    drum = RotaryAssemblyLayer(
        radius=5,
        number=1,
    )
    assert calculate_drum_surface_in_core(drum, core_desc, drum_desc) == 0

    drum2 = RotaryAssemblyLayer(
        radius=4,
        number=1,
    )

    with pytest.raises(Exception):
        calculate_drum_surface_in_core(drum2, core_desc, drum_desc)

    drum3 = RotaryAssemblyLayer(
        radius=6,
        number=1,
    )
    assert calculate_drum_surface_in_core(drum3, core_desc, drum_desc) > 0


def test_drum_surface_in_core_correct_when_intersection_is_half():
    drum_desc = RotaryAssemblyDesc(
        assembly_core_distance=10,
        assembly_core_margin=0,
    )
    core_desc = compute_core_desc(
        core_radius=10,
        core_height=1,
        outer_core_assembly=AssemblySections(parts=[]),
    )
    drum = RotaryAssemblyLayer(
        radius=10,
        number=1,
    )
    assert calculate_drum_surface_in_core(
        drum, core_desc, drum_desc
    ) == 2 * 10 * math.acos(0.5)
