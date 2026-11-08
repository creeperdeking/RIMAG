# Reactor slice app

Streamlit calculator for one hollow-disk reactor slice. `README.md` only explains how to run the app. Trust `geometry.py` and `app.py` for the layout.

Run from this directory: `python -m streamlit run app.py` (often already on `http://localhost:8501`). Importing `app.py` starts the Streamlit script. Use `geometry.py` for calculations.

## Layout

The disk is an annulus. Inner diameter is `a + reflector + b`, rim width is `w`.

```
R_i = (a + reflector + b) / 2
R_o = R_i + w
```

Around the rim, fuel is centered at the top. On each side the order is fuel, reflector, shielding, TPV. TPV is the zone opposite the fuel.

`a` is the shielding thickness. `b` is a percentage of `a` (slider `b_pct`, 1–100). The fuel/TPV slider (`ratio_pct`, 10–50) is the fuel area divided by the TPV area, not a share of the whole disk. `percent_fuel_for_ratio` turns that ratio into the fuel angle.

Reflector and shielding angles come from their thicknesses. The chord between a sector's two inner corners equals that thickness:

```
2 * R_i * sin(phi / 2) = thickness
```

Fuel and TPV share whatever angle is left. Reported areas are the annular sectors only. The filled hole is not added to them.

## Hole

Both center fills are flat chords, drawn in the local frame with fuel at +y, then rotated. `center_shield_cut` returns the fuel side of the inner disk above a horizontal line.

**Shield.** The edge is the line further toward the TPV of these two:

- the chord through the inner-rim points where the TPV meets the shielding
- a parallel line whose distance to the nearest fuel point (the fuel inner corners) is shielding thickness plus reflector thickness

```python
y_fuel = R_i * cos(fuel_angle / 2)
y_meet = -R_i * cos(opposite_angle / 2)
y_shield = min(y_fuel - (a + reflector), y_meet)
```

The edge is never short of that TPV junction. When the clearance line is the further one, it crosses the inner rim past the junction. Do not pull it back toward the fuel, and do not use `a` alone as the clearance.

**Reflector.** A straight chord through the two inner-rim points where the reflector meets the shielding. It sits against the fuel and has no clearance of its own. Do not inset it by the reflector thickness, and do not turn it into a wedge.

```python
y_refl = R_i * cos(fuel_angle / 2 + reflector_angle)
```

Draw the shield first and the reflector on top of it.

## Power and columns

Slice power uses both TPV faces: `2 * density * TPV area * columns`. The layer designer sums layer thicknesses in cm; that sum is the slice pitch. Stack power is the slice power times `stack height / pitch`.

Columns are 1, 2, or 3 disks whose fuel zones point at a shared center and whose rims touch. Two disks are stacked and face each other. Three sit on an equilateral triangle.

## UI choices already made

Keep these unless the user asks to change them.

- Title stays in the sidebar. The main view is the drawing plus a compact results panel on the right.
- Names are Fuel, Reflector, TPV, and Shielding. Results omit angles and the fuel/TPV ratio. They include disk diameter `2 * R_o`.
- Slider values live in the page address so a reload restores them.
- The red thickness chords follow "Show dimension lines", same as the other dimension marks.
