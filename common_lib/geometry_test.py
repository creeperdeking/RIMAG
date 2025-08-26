from common_lib.assemblies_types import Assembly, AssemblySections
from common_lib.geometry import check_assembly_compatibility


def test_check_assembly_compatibility_1():
    assembly1 = AssemblySections(
        parts=[
            Assembly(
                thickness=0.3633333333,
                is_emitter=False,
            ),
            Assembly(
                thickness=0.02,
                is_emitter=False,
            ),
            Assembly(
                thickness=0.9,
                is_emitter=True,
            ),
            Assembly(
                thickness=0.02,
                is_emitter=False,
            ),
            Assembly(
                thickness=0.48,
                is_emitter=False,
            ),
            Assembly(
                thickness=0.48,
                is_emitter=False,
            ),
            Assembly(
                thickness=0.02,
                is_emitter=False,
            ),
            Assembly(
                thickness=0.9,
                is_emitter=True,
            ),
        ]
    )
    assembly2 = AssemblySections(
        parts=[
            Assembly(
                thickness=0.3833333333,
                is_emitter=False,
            ),
            Assembly(
                thickness=0.9,
                is_emitter=True,
            ),
            Assembly(
                thickness=0.5,
                is_emitter=False,
            ),
            Assembly(
                thickness=0.5,
                is_emitter=False,
            ),
            Assembly(
                thickness=0.9,
                is_emitter=True,
            ),
        ]
    )
    check_assembly_compatibility(assembly1, assembly2, 1)


def test_check_assembly_compatibility():
    assembly1 = AssemblySections(
        parts=[
            Assembly(
                thickness=0.363333333,
                is_emitter=False,
            ),
            Assembly(
                thickness=0.02,
                is_emitter=False,
            ),
            Assembly(
                thickness=0.9,
                is_emitter=True,
            ),
            Assembly(
                thickness=0.02,
                is_emitter=False,
            ),
            Assembly(
                thickness=0.48,
                is_emitter=False,
            ),
            Assembly(
                thickness=0.48,
                is_emitter=False,
            ),
            Assembly(
                thickness=0.02,
                is_emitter=False,
            ),
            Assembly(
                thickness=0.9,
                is_emitter=True,
            ),
            Assembly(
                thickness=0.02,
                is_emitter=False,
            ),
            Assembly(
                thickness=0.363333333,
                is_emitter=False,
            ),
        ]
    )
    assembly2 = AssemblySections(
        parts=[
            Assembly(
                thickness=0.383333333,
                is_emitter=False,
            ),
            Assembly(
                thickness=0.9,
                is_emitter=True,
            ),
            Assembly(
                thickness=0.5,
                is_emitter=False,
            ),
            Assembly(
                thickness=0.5,
                is_emitter=False,
            ),
            Assembly(
                thickness=0.9,
                is_emitter=True,
            ),
            Assembly(
                thickness=0.383333333,
                is_emitter=False,
            ),
        ]
    )
    check_assembly_compatibility(assembly1, assembly2, 1)
