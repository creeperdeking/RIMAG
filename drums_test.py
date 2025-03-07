from drums import (
    calculate_drum_surface_in_core,
    DrumDesc,
    DrumLayer,
    compute_core_desc,
)
import pytest
import math


def test_drum_surface_in_core_zero_when_intersection_is_zero():
    drum_desc = DrumDesc(
        drum_core_distance=10,
        drum_core_margin_inner=0,
        drum_core_margin_outer=0,
    )
    core_desc = compute_core_desc(
        core_radius=5,
        core_height=1,
        reflector_thickness=0,
        neutron_shield_thickness=0,
    )
    drum = DrumLayer(
        radius=5,
        number=1,
    )
    assert calculate_drum_surface_in_core(drum, core_desc, drum_desc) == 0

    drum2 = DrumLayer(
        radius=4,
        number=1,
    )

    with pytest.raises(Exception):
        calculate_drum_surface_in_core(drum2, core_desc, drum_desc)

    drum3 = DrumLayer(
        radius=6,
        number=1,
    )
    assert calculate_drum_surface_in_core(drum3, core_desc, drum_desc) > 0


def test_drum_surface_in_core_correct_when_intersection_is_half():
    drum_desc = DrumDesc(
        drum_core_distance=10,
        drum_core_margin_inner=0,
        drum_core_margin_outer=0,
    )
    core_desc = compute_core_desc(
        core_radius=10,
        core_height=1,
        reflector_thickness=0,
        neutron_shield_thickness=0,
    )
    drum = DrumLayer(
        radius=10,
        number=1,
    )
    assert calculate_drum_surface_in_core(
        drum, core_desc, drum_desc
    ) == 2 * 10 * math.acos(0.5)
