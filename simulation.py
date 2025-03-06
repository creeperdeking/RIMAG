from drums import DrumDesc, compute_core_desc

from geometry import (
    AssemblySectionDesc,
    MaterialChoice,
    define_geometry,
    calculate_assembly_thickness,
)

from simlib import render_geometry, criticality_simulation


fuel_thicc = 0.45
assembly_section = AssemblySectionDesc(
    fuel_thickness=fuel_thicc,
    fuel_cladding_gap=fuel_thicc * 0.15 / 2,
    cladding_thickness=0.03,
    cladding_drum_gap=0.07,
    drum_thickness=0.01,
)

print("thicc")
print(calculate_assembly_thickness(assembly_section))

core_diameter = 120
geometry, universe = define_geometry(
    compute_core_desc(
        core_radius=core_diameter / 2,
        core_height=core_diameter,
        reflector_thickness=20,
        neutron_shield_thickness=20,
        gamma_shield_thickness=10,
    ),
    DrumDesc(
        drum_core_distance=core_diameter + 30 / 2,
        drum_core_margin_inner=2,
        drum_core_margin_outer=0.5,
    ),
    MaterialChoice(
        neutron_shield="Boron Carbide",
        reflector="Molybdenum",
        fuel="Plutonium Carbide",
        cladding="Molybdenum",
        drum="Molybdenum",
        moderator="Void",
    ),
    assembly_section=assembly_section,
    half_drum=True,
)


render = False
if render:
    render_geometry(
        universe,
        universe_radius=(100),
        pixels=(2500, 2500),
        basis="xy",
        origin=(0, 0, 0.0),
    )
else:
    criticality_simulation(
        geometry,
        universe,
    )
