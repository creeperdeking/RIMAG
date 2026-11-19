# Periodic z-cones

OpenMC 0.16.0 only applies a periodic boundary to planes. A tilted RIMAG pitch is a cone, so the web app used to fake that boundary: it stacked many copies of one pitch (`boundary_layer_*`) inside a flat periodic slab, enough copies for the cone to cross the slab out at the outer radius. At 15° that stack is about 200 shells. At 2° it is already several times one shell.

The patch teaches OpenMC to translate a neutron between two coaxial z-cones. The web-app geometry then keeps a single shell. `conical_pitch = 0` still uses periodic planes. The paper geometry (`common_lib/geometry.py`, `simulation_paper.py`) is unchanged.

A 2° keff on the calculator setup matched the stacked-shell result and ran about 2–3× faster. That comparison was made in the app. The checks below are the ones run while building the patch.

## Patch

The published tree is [creeperdeking/openmc](https://github.com/creeperdeking/openmc), branch `periodic-zcone`, forked from tag `v0.16.0` (`617d35a5063c57796b43428bc401e627d2011046`). `docker/openmc-periodic-zcone.patch` is that same diff. The RIMAG `Dockerfile` clones the fork and fetches the tag so CMake still reports 0.16.0. It does not apply the patch again. MPI is off. The Python package is installed from `/opt/openmc`, not from the cmake build directory. Build and image instructions are in the fork’s `PERIODIC_ZCONE.md` and `Dockerfile.periodic`.

Two z-cones are the same surface translated along their axis when they share `x0`, `y0`, and `r²` and their apexes differ. The existing translational periodic condition already moves a particle by a fixed vector and leaves its direction alone. The patch sets that vector to `(0, 0, z0_partner − z0_hit)` and builds the pair both ways, so the two jumps are opposite.

Stock OpenMC writes a `ZCone` as a generic quadric. A periodic cone is written as `type="z-cone"` with coefficients `x0 y0 z0 r2`, plus `periodic_surface_id`. Planes keep their old pairing rules.

Files:

| File | Change |
| --- | --- |
| `src/boundary_condition.cpp` | `TranslationalPeriodicBC` accepts two coaxial z-cones of equal opening angle and stores the apex offset as the translation. A cone paired with anything else is a fatal error. |
| `src/surface.cpp` | `prepare_boundary_conditions` builds that translational condition for a z-cone pair and skips the plane-normal test. |
| `openmc/surface.py` | `Surface.periodic_surface` accepts a `ZCone` partner. `ZCone.to_xml_element` keeps `type="z-cone"` when the boundary is periodic. |
| `tests/unit_tests/test_surface.py` | Pairing two z-cones succeeds. Pairing a z-cone with a sphere or a z-plane raises `TypeError`. |

The image is built with `OPENMC_BUILD_TESTS=OFF`, so that unit test is in the patch and was not executed inside `rimag:research-paper`.

The cones must sit on the root universe. A periodic jump is discontinuous, and OpenMC drops a particle whose periodic surface is inside a fill. The cell that owns the pair has to be a simple region. A union stores the surface sense from the direction, which does not match the sense the periodic handler copies.

A z-cone is a double cone, and its normal is zero at the apex. A neutron that hits an apex is teleported to the other apex, where the shell has zero thickness, and the cell search correctly rejects it. That hit has measure zero everywhere except a ray aimed at the tip in the apex plane. The transport tests put a vacuum cylinder inside the inner cone so a radial ray dies before the tip. There is no special case in the patch.

## Web-app geometry

`app_slice_design/geometry.py`, only when `conical_pitch` is not zero:

- One slice fill per column. No `boundary_layer_*` stack.
- Root cell per column: the column cylinder, outside the lower cone and inside the upper cone. Both cones are periodic, same axis `(cx, cy)`, same `r² = 1/tan²(α)`, apexes at `z_shift ± half_period`.
- `z_shift = r_mid · tan(α)`, so the sheet at the fuel mid-radius and material z = 0 passes through the world origin. The default source `Point((0,0,0))` still starts in fuel.
- The fill is translated by `(cx, cy, z_shift)`. Its first and last axial bounds are left open. A coincident copy of the periodic cone would be merged (`merge_surfaces=True`, `surface_precision=5`) and the periodic boundary would be lost. Internal sheets stay `ZConeOneSided(up=False)`.
- Vacuum z-planes sit 1 cm outside the shell. The lowest point is the lower cone at `r_out`; the highest is the upper apex.
- `stack_m` is still only the engineering height used for inventory. Transport is one period, `pitch / cos(α)`.

At 0° the root cell is still the column cylinder between periodic z-planes, filled with one `boundary_layer`.

## Volumes

Stochastic volume samples an axis-aligned box. The tilted shell’s box is mostly empty, and a 0.05 cm void in the narrow absorber sector is about 235 cm³. Ten million samples hit it ~65 times (12.6%), which tripped the 5% check on `shield_absorber_1_Void`.

An annulus between two equal-angle cones has a constant vertical gap `t / cos(α)`. Those sheet volumes are now `sector area × that gap`, times the number of columns, because one cell object is instantiated once per column. `volume / t` is the conical face area, which is what the power calculation already divides by. `stochastic_volume_calculation` samples only cells that do not already have a volume: the inner hole pieces and the outer void.

## Tests

All transport and volume checks ran in `rimag:research-paper` except the first algorithm check, which ran in a throwaway image built from OpenMC `develop` before the 0.16.0 port. The scripts lived under the temp directory and are not in the repo.

### Cone jump, develop, then again on 0.16.0

Shell between two cones, `r² = 4` (so `R = 2|z − z0|`), apexes at z = −20 and z = −10. Vacuum for `R < 10` and `R > 50`.

| Start | Direction | Result |
| --- | --- | --- |
| `(20.1, 0, 0)` | `(−1, 0, 0)` | Hits the inner sheet at x = 20 and reappears at z = −10. |
| `(39.9, 0, 0)` | `(+1, 0, 0)` | Hits the outer sheet at x = 40 and reappears at z = +10. |

Both jumps moved z by exactly one apex offset and left x unchanged at the hit. No particle was lost. The same box with periodic planes wrapped 60 times and then leaked out a corner, which is the plane condition still working.

The first develop run lost the inward neutron after a second jump, from `(20, 0, −10)` to the other apex `(0, 0, −20)`. That point is the tip, not a failed translation. The inner vacuum cylinder removes the ray before the tip. A debug print in `handle_particle` confirmed the first jump, and it was removed before the 0.16.0 patch.

The 0.16.0 image reports version `0.16.0`, commit `617d35a`. The first image build compiled and then failed because `pip install` ran inside `build/`. The install step is a separate `pip install /opt/openmc`. The rebuild succeeded, and the jump test above passed in that image.

### App geometry at 15°

Built from `make_app_slice_geometry` with a 2 cm material pitch (0.1 cm UO2 + 1.9 cm graphite in fuel, 2 cm graphite elsewhere).

- Pitch 0 exports periodic z-planes and no z-cone, and prints `1× boundary_layer`.
- Pitch 15°, three columns, exports six periodic z-cones (a pair per column).
- Pitch 15°, one column. Period 2.07055 cm. One neutron from `(0, 0, 0)` with direction `(0, 0.05, 1)` normalized. It crossed by one period 832 times (1667 track samples) and left through the outer vacuum cylinder. Leakage 1. No lost particles.

A first look at a purely vertical track seemed to bounce between z = −1.035 and z = −0.932. Those samples are the post-jump landing on the lower cone and the next material sheet. The flight up to the upper cone plus the jump of −2.071 cm is stored as one step. The neutron was wrapping, not stuck.

### Volumes on the 2° calculator setup

`runs/default/app_slice_run.json`: pitch 2.05 cm, `conical_pitch` 2°, one column. Absorber area from the layout, gap 0.05 cm, `1/cos(2°)`.

| Cell | Volume | Expected |
| --- | --- | --- |
| `shield_absorber_1_Void`, 1 column, 2° | 235.106819 cm³ | sector area × 0.05 / cos(2°) |
| same cell, 3 columns | 705.320458 cm³ | 3 × the one-column volume |
| same cell, pitch 0° | 234.963599 cm³ | sector area × 0.05 |
| UO2, 1 column, 2° | 1677.103219 cm³ | fuel area × 0.0347 / cos(2°) |

`hole_absorber`, `hole_moderator`, `hole_void`, and `world_void` stay on the sampler. At 2 million samples every one of them was under 5% uncertainty. The production run uses 10 million.
