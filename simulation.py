class AssemblySectionDesc:
    fuel_thickness: float
    fuel_cladding_gap: float
    cladding_thickness: float
    cladding_emitter_gap: float
    emitter_thickness: float


def assembly_section_thickness(section: AssemblySectionDesc) -> float:
    return (
        section.fuel_thickness
        + section.fuel_cladding_gap * 2
        + section.cladding_thickness * 2
        + section.cladding_emitter_gap * 2
        + section.emitter_thickness
    )


class CoreDesc:
    core_diameter: float
    core_height: float
    shielding_thickness: float
