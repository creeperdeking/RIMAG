from drums import DrumDesc, compute_core_desc
from geometry_utils import (
    AssemblySections,
    Assembly,
)
from geometry import (
    MaterialChoice,
    define_geometry,
    calculate_assembly_thickness,
)

from simlib import render_geometry, criticality_simulation

core_diameter = 120
fuel_thicc = 0.45

fuel_thickness = fuel_thicc
fuel_cladding_gap = fuel_thicc * 0.15 / 2
cladding_thickness = 0.03
cladding_drum_gap = 0.07
drum_thickness = 0.01

material_choice = MaterialChoice(
    moderator="Void",
    neutron_shield="Boron Carbide",
    reflector="Molybdenum",
    fuel="Plutonium-Uranium Carbide",
    cladding="Molybdenum",
    drum="Tungsten",
)

drum_assembly = AssemblySections(
    parts=[
        ### Void
        Assembly(
            material="Void",
            thickness=cladding_drum_gap,
        ),
        ### Drum
        Assembly(
            material=material_choice.drum,
            thickness=drum_thickness,
        ),
        ### Void
        Assembly(
            material="Void",
            thickness=cladding_drum_gap,
        ),
    ],
)


inner_assembly_unique_parts = AssemblySections(
    parts=[
        ### Cladding
        Assembly(
            material=material_choice.cladding,
            thickness=cladding_thickness,
        ),
        ### Void
        Assembly(
            material="Void",
            thickness=fuel_cladding_gap,
        ),
        ### Fuel
        Assembly(
            material=material_choice.fuel,
            thickness=fuel_thickness,
        ),
        ### Void
        Assembly(
            material="Void",
            thickness=fuel_cladding_gap,
        ),
        ### Cladding
        Assembly(
            material=material_choice.cladding,
            thickness=cladding_thickness,
        ),
    ],
)

inner_assembly_unique_parts_thickness = calculate_assembly_thickness(
    inner_assembly_unique_parts
)

inner_assembly_desc = AssemblySections(
    parts=[
        *drum_assembly.parts,
        *inner_assembly_unique_parts.parts,
    ],
)

assembly_desc_last = AssemblySections(
    parts=[*drum_assembly.parts],
)

outer_assembly_desc_reflector = AssemblySections(
    parts=[
        *drum_assembly.parts,
        ### Reflector
        Assembly(
            material=material_choice.reflector,
            thickness=inner_assembly_unique_parts_thickness,
        ),
    ],
)

outer_assembly_desc_absorber = AssemblySections(
    parts=[
        *drum_assembly.parts,
        ### Neutron Shield
        Assembly(
            material=material_choice.neutron_shield,
            thickness=inner_assembly_unique_parts_thickness,
        ),
    ],
)

core_desc = compute_core_desc(
    core_radius=core_diameter / 2,
    core_height=core_diameter,
    reflector_thickness=20,
    neutron_shield_thickness=20,
)

drum_desc = DrumDesc(
    drum_core_distance=core_diameter / 2 + 20,
    drum_core_margin_inner=2,
    drum_core_margin_outer=0.5,
)


print("thicc: ", calculate_assembly_thickness(inner_assembly_desc))

geometry, universe = define_geometry(
    assembly_section_inner=inner_assembly_desc,
    assembly_section_reflector=outer_assembly_desc_reflector,
    assembly_section_absorber=outer_assembly_desc_absorber,
    assembly_section_last=assembly_desc_last,
    half_drum=True,
    core_desc=core_desc,
    drum_desc=drum_desc,
    material_choice=material_choice,
)


render = False
if render:
    render_geometry(
        universe,
        universe_radius=(100),
        pixels=(1500, 1500),
        basis="xy",
        origin=(0, 0, 0.0),
        geometry=geometry,
    )
else:
    criticality_simulation(
        geometry,
        universe,
    )
