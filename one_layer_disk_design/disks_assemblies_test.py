from disk_design.disks_assemblies import calculate_disks_emitter_volume
from disk_design.disks_assemblies import (
    AssemblySections,
    CoreDesc,
    DiskAssemblyLayer,
    RotaryAssemblyDesc,
)

from common_lib.assemblies import Assembly, EmitterPlaceholder


def test_calculate_disks_emitter_volume():

    assert (
        calculate_disks_emitter_volume(
            assembly_section=AssemblySections(
                parts=[
                    EmitterPlaceholder(thickness=0.48, is_emitter=True),
                    Assembly(
                        thickness=0.05,
                        material="Zirconium",
                        is_fuel=False,
                        is_emitter=False,
                    ),
                    Assembly(
                        thickness=1.2,
                        material="Light Water",
                        is_fuel=False,
                        is_emitter=False,
                    ),
                    Assembly(
                        thickness=0.05,
                        material="Zirconium",
                        is_fuel=False,
                        is_emitter=False,
                    ),
                    EmitterPlaceholder(thickness=0.48, is_emitter=True),
                    Assembly(
                        thickness=0.16,
                        material="Graphite",
                        is_fuel=False,
                        is_emitter=False,
                    ),
                    Assembly(
                        thickness=0.03,
                        material="Uranium Oxy-Carbide",
                        is_fuel=True,
                        is_emitter=False,
                    ),
                    Assembly(
                        thickness=0.16,
                        material="Graphite",
                        is_fuel=False,
                        is_emitter=False,
                    ),
                ]
            ),
            drums=[
                DiskAssemblyLayer(radius=103.0, height=-24.0, number=0),
                DiskAssemblyLayer(radius=103.0, height=-21.39, number=1),
                DiskAssemblyLayer(radius=103.0, height=-18.78, number=2),
                DiskAssemblyLayer(radius=103.0, height=-16.17, number=3),
                DiskAssemblyLayer(radius=103.0, height=-13.560000000000002, number=4),
                DiskAssemblyLayer(radius=103.0, height=-10.950000000000003, number=5),
                DiskAssemblyLayer(radius=103.0, height=-8.340000000000003, number=6),
                DiskAssemblyLayer(radius=103.0, height=-5.730000000000004, number=7),
                DiskAssemblyLayer(radius=103.0, height=-3.120000000000004, number=8),
                DiskAssemblyLayer(radius=103.0, height=-0.5100000000000042, number=9),
                DiskAssemblyLayer(radius=103.0, height=2.0999999999999956, number=10),
                DiskAssemblyLayer(radius=103.0, height=4.7099999999999955, number=11),
                DiskAssemblyLayer(radius=103.0, height=7.319999999999995, number=12),
                DiskAssemblyLayer(radius=103.0, height=9.929999999999994, number=13),
                DiskAssemblyLayer(radius=103.0, height=12.539999999999994, number=14),
                DiskAssemblyLayer(radius=103.0, height=15.149999999999993, number=15),
                DiskAssemblyLayer(radius=103.0, height=17.759999999999994, number=16),
                DiskAssemblyLayer(radius=103.0, height=20.369999999999994, number=17),
            ],
            drum_desc=RotaryAssemblyDesc(
                assembly_core_distance=78, assembly_core_margin=1
            ),
            core_desc=CoreDesc(
                core_radius=25,
                core_height=50,
                outer_core_radius=125,
                outer_core_height=250,
            ),
            half_assembly=False,
        )
        == 2
    )
