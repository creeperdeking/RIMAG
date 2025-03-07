from drums import DrumDesc, compute_core_desc
from geometry_utils import (
    AssemblySections,
    Assembly,
)
from geometry import (
    MaterialChoice,
    define_geometry,
    calculate_assembly_thickness,
    GeometrySettings,
)
from drums import (
    calculate_drums_emissive_surface_in_core,
    radiative_heat_flux_between_plates,
)
from simlib import render_geometry, criticality_simulation

core_diameter = 100
cladding_thickness = 0.03
fuel_thickness = 1.0
moderator_thickness = fuel_thickness / 1
fuel_drum_gap = 0.07
drum_thickness = 0.01

render = False
keff_simulation = False
print_core_characteristics = True
half_drum = True

material_choice = MaterialChoice(
    moderator="Light Water",
    neutron_shield="Boron Carbide",
    reflector="Graphite",
    fuel="TRISO",
    cladding="Aluminum",
    drum="Molybdenum",
)

drum_assembly = AssemblySections(
    parts=[
        ### Void
        Assembly(
            material="Void",
            thickness=fuel_drum_gap,
        ),
        ### Drum
        Assembly(
            material=material_choice.drum,
            thickness=drum_thickness,
        ),
        ### Void
        Assembly(
            material="Void",
            thickness=fuel_drum_gap,
        ),
    ],
)


inner_assembly_unique_parts1 = AssemblySections(
    parts=[
        ### Cladding
        Assembly(
            material=material_choice.cladding,
            thickness=cladding_thickness,
        ),
        ### Moderator
        Assembly(
            material=material_choice.moderator,
            thickness=moderator_thickness,
        ),
        ### Cladding
        Assembly(
            material=material_choice.cladding,
            thickness=cladding_thickness,
        ),
    ],
)

inner_assembly_unique_parts2 = AssemblySections(
    parts=[
        ### Fuel
        Assembly(
            material=material_choice.fuel,
            thickness=fuel_thickness,
        ),
    ],
)

inner_assembly_unique_parts_complete = AssemblySections(
    parts=[
        *inner_assembly_unique_parts1.parts,
        *drum_assembly.parts,
        *inner_assembly_unique_parts2.parts,
    ],
)

inner_assembly_unique_parts1_thickness = calculate_assembly_thickness(
    inner_assembly_unique_parts1
)

inner_assembly_unique_parts2_thickness = calculate_assembly_thickness(
    inner_assembly_unique_parts2
)

core_desc = compute_core_desc(
    core_radius=core_diameter / 2,
    core_height=core_diameter,
    reflector_thickness=30,
    neutron_shield_thickness=30,
)

drum_desc = DrumDesc(
    drum_core_distance=core_desc.core_radius
    + (core_desc.outer_core_radius - core_desc.core_radius) / 2
    + 3,
    drum_core_margin_inner=2,
    drum_core_margin_outer=0.5,
)

geometry_settings = GeometrySettings(
    assembly_section_inner=AssemblySections(
        parts=[
            *drum_assembly.parts,
            *inner_assembly_unique_parts_complete.parts,
        ],
    ),
    assembly_section_reflector=AssemblySections(
        parts=[
            *drum_assembly.parts,
            ### Reflector
            Assembly(
                material=material_choice.reflector,
                thickness=inner_assembly_unique_parts1_thickness,
            ),
            *drum_assembly.parts,
            ### Reflector
            Assembly(
                material=material_choice.reflector,
                thickness=inner_assembly_unique_parts2_thickness,
            ),
        ],
    ),
    assembly_section_absorber=AssemblySections(
        parts=[
            *drum_assembly.parts,
            ### Reflector
            Assembly(
                material=material_choice.neutron_shield,
                thickness=inner_assembly_unique_parts1_thickness,
            ),
            *drum_assembly.parts,
            ### Reflector
            Assembly(
                material=material_choice.neutron_shield,
                thickness=inner_assembly_unique_parts2_thickness,
            ),
        ],
    ),
    assembly_section_last=AssemblySections(
        parts=[*drum_assembly.parts],
    ),
    half_drum=half_drum,
    core_desc=core_desc,
    drum_desc=drum_desc,
    material_choice=material_choice,
)


geometry, universe, drums = define_geometry(geometry_settings)

if print_core_characteristics:
    print()
    print(
        "thicc: ",
        calculate_assembly_thickness(geometry_settings.assembly_section_inner),
    )

    print(core_desc)

    emissive_surface = (
        calculate_drums_emissive_surface_in_core(drums, drum_desc, core_desc) / 10000
    )
    print("half drum", half_drum)

    print("emissive_surface", emissive_surface * (2 if half_drum else 1))

    hot_temp = 2020 + 273
    cold_temp = 1750 + 273

    radiative_flux = radiative_heat_flux_between_plates(hot_temp, cold_temp, 0.9, 0.9)
    print("Radiative flux", radiative_flux)

    print("core power", radiative_flux * emissive_surface / 1000000)
    print()


if render:
    render_geometry(
        universe,
        universe_radius=(core_desc.outer_core_radius),
        pixels=(2500, 2500),
        basis="xy",
        origin=(0, 0, 0.0),
        geometry=geometry,
    )

if keff_simulation:
    criticality_simulation(
        geometry,
        universe,
    )
