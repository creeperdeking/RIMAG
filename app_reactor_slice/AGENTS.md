# Reactor slice app

Streamlit calculator for one hollow-disk reactor slice. `README.md` only explains how to run the app. Trust `geometry.py` for the layout math.

Run from this directory: `python -m streamlit run app.py` (often already on `http://localhost:8501`). `app.py` is the entry point: sidebar, power totals, and the three tabs. Tab bodies live in `tabs/overview.py`, `tabs/fuel.py`, and `tabs/designer.py`. Shared Streamlit helpers live in `ui/`. Use `geometry.py` for calculations.

## Layout

The disk is an annulus. Inner diameter is `a + reflector + absorber + b`, rim width is `w`.

```
R_i = (a + reflector + absorber + b) / 2
R_o = R_i + w
```

The curved absorber in the hole already has radial thickness `absorber`, so the diameter is not grown further.

Around the rim, fuel is centered at the top. On each side the order is fuel, reflector, shield moderator, shield absorber, TPV. TPV is the zone opposite the fuel.

`a` is the shield moderator thickness. `absorber` is the shield absorber thickness (slider `abs`, 0.01–0.5 m). `reflector` is the reflector thickness (slider `refl`, 0.1–1 m). `b` is a percentage of `a` (slider `b_pct`, 1–100). The fuel/TPV slider (`ratio_pct`, 10–50) is the fuel area divided by the TPV area, not a share of the whole disk. `percent_fuel_for_ratio` turns that ratio into the fuel angle at the diameter being solved.

Reflector, shield moderator, and shield absorber angles come from their thicknesses. The chord between a sector's two inner corners equals that thickness:

```
2 * R_i * sin(phi / 2) = thickness
```

Fuel and TPV share whatever angle is left. Reported areas are the annular sectors only. The filled hole is not added to them.

## Hole

Moderator and reflector fills are flat chords, drawn in the local frame with fuel at +y, then rotated. `center_shield_cut` returns the fuel side of the inner disk above a horizontal line. `center_cuts` is the source of those chord positions. Draw the moderator, then the reflector, then the absorber so the absorber's curved front is not covered.

**Shield moderator.** The edge is the line further toward the TPV of these two:

- the chord through the inner-rim points where the absorber meets the shield moderator
- a parallel line whose distance to the nearest fuel point (the fuel inner corners) is shield moderator thickness plus reflector thickness

```python
y_fuel = R_i * cos(fuel_angle / 2)
y_mod = -R_i * cos(opposite_angle / 2 + absorber_angle)
y_shield = min(y_fuel - (a + reflector), y_mod)
```

The edge is never short of that absorber junction. When the clearance line is the further one, it crosses the inner rim past the junction. Do not pull it back toward the fuel, and do not use `a` alone as the clearance.

**Shield absorber.** `absorber_front` is the outline. It is every point of the inner disk within distance `absorber` of the TPV inner arc, so a ray from a TPV cell that stays in the hole crosses at least that much absorber. The far edge is the concentric arc of radius `R_i - absorber`. Each corner is a circular arc of radius `absorber` centered on the TPV corner, and that arc meets the inner circle where the absorber rim meets the moderator. With zero absorber, skip the region. Do not replace this outline with a flat chord.

**Reflector.** A straight chord through the two inner-rim points where the reflector meets the shield moderator. It sits against the fuel and has no clearance of its own. Do not inset it by the reflector thickness, and do not turn it into a wedge.

```python
y_refl = R_i * cos(fuel_angle / 2 + reflector_angle)
```

## Power and columns

The Fuel setup tab takes enrichment in percent, a packing fraction from 1% to 30%, an HM fraction per particle from 20% to 60%, and a reload fraction of 1/2, 1/3, 1/4, or 1/5. The fuel is cylinders. Cylinder diameter, default 10 mm, is the fuel-layer thickness. A wall margin keeps particles inside the cylinder, and compact spacing, default 1 mm, is the gap between cylinders. The packing fraction applies in the inner circle. Heavy metal in the simplified stack is that particle volume times the HM fraction per particle, spread over a cell one diameter thick and one diameter plus the spacing wide. The two graphite layers share the rest. The fuel tab shows a to-scale compact cross section and the smeared stack on the right. Burnup in MWd/kgHM is the enrichment fraction times 1200, rounded to the nearest integer. The left panel has a TPV efficiency slider from 10% to 50%. Cell power density is in W/cm², from 0.01 to 3, and is electrical. Slice power uses both TPV faces: `2 * density * 10 * TPV area * columns`, with area in m² so the result stays in kW. The layer designer edits the disk once, plus the reflector, shield moderator, shield absorber, and TPV stacks. The fuel stack is set from the Fuel setup tab, where burnup and burnup time share one card, and it still appears in the thickness chart. Layer colors, compositions, and densities come from `common_lib/materials.py`. The bar chart and each stack list them. Uranium mass uses that same composition and density. The disk is added on top of each stack. Those five composed thicknesses must match. That shared thickness, in cm, is the slice pitch. If the totals differ, warn and do not treat a sum or a single stack as the pitch. Stack power is the slice power times `stack height / pitch`. Results show that stack power and the core thermal power, which is the stack power divided by the TPV efficiency. They do not show power per slice.

Columns are 1, 2, or 3 disks whose fuel zones point at a shared center and whose rims touch. Two disks are stacked and face each other. Three sit on an equilateral triangle.

## UI choices already made

Keep these unless the user asks to change them.

- Title stays in the sidebar. The main view is the drawing plus a compact results panel on the right.
- Names are Fuel, Reflector, TPV, Shield moderator, and Shield absorber. Results omit angles and the fuel/TPV ratio. They include disk diameter `2 * R_o`.
- Slider values live in the page address so a reload restores them. Fuel enrichment, packing fraction, HM fraction per particle, cylinder diameter, wall margin, compact spacing, reload fraction, TPV efficiency, and the open tab are stored the same way. Enrichment, packing fraction, HM fraction per particle, cylinder diameter, wall margin, compact spacing, reload fraction, and TPV efficiency are also stored in saved configurations.
- TPV efficiency stays in the left panel, from 10% to 50%. Fuel enrichment, packing fraction, HM fraction per particle, cylinder diameter, wall margin, compact spacing, and the reload fraction stay on the Fuel setup tab.
- Left-panel sliders stay compact: the value is on the right of the label, and the track sits directly underneath.
- The red thickness chords follow "Show dimension lines", same as the other dimension marks.
