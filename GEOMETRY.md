# Geometry

The OpenMC model is built by `app_slice_design/geometry.py`. `simulation_app_slice.py` calls `make_app_slice_geometry` with the calculator setup: the hollow-disk sectors from `app_slice_design/layout.py` and the layer stacks drawn on the page.

`conical_pitch = 0` uses periodic planes. A nonzero pitch uses periodic z-cones when the OpenMC build supports them, and otherwise stacks cone sheets inside one periodic slab. The bounding box and the render view are passed into `start_program` with the geometry.
