# RIMAEL

Commands for rebuilding the Docker image, viewing the geometry in `runs/default`, and plotting the curves from the end of `README_paper.md`. Paper reproduction itself is described in `README_paper.md`.

Run the commands below from the repository root in PowerShell, unless a section says otherwise. Docker Desktop must be running, and `.env` must set `OPENMC_DATA_DIR` to the folder that contains `cross_sections.xml` (use `/` in that path on Windows).

## Rebuild the Docker image

`clean_build_docker.sh` rebuilds `rimag:research-paper` from the files currently in this repository. It runs `docker compose build --no-cache`, so Docker copies the working tree again instead of reusing a cached layer.

```powershell
bash ./clean_build_docker.sh
```

Use `./`, not `.\`. The `bash` command on Windows is WSL, and a backslash is treated as an escape, so `.\clean_build_docker.sh` is looked up as `.clean_build_docker.sh`.

This updates the image only. The container executes the copy already stored in `runs/default`, and that folder is left as it is.

## View the geometry in runs/default

`show_geometry.sh` opens `runs/default/geometry.xml` and `runs/default/materials.xml` with openmc-plotter. The plotter is the WSL program at `~/miniforge3/envs/openmc-plot/bin/openmc-plotter`. Set `OPENMC_PLOTTER` if it lives somewhere else. The script points OpenMC at `cross_sections.xml` inside the `OPENMC_DATA_DIR` folder from `.env`, and opens a writable copy of the model XML so the plotter does not need to overwrite `runs/default/summary.h5`. Each material is drawn with the `color` set for that name in `common_lib/materials.py`. Numbered copies such as `Graphite 2` keep the base material color. PowerShell stays busy until the plotter window is closed.

```powershell
bash ./show_geometry.sh
```

Those XML files are produced by a render run. Put a parameter file in `runs/default` (for example `my_params.json`) with `run_mode` set to `render`:

```json
{
    "nsm_material": "Graphite",
    "nsm_thickness": 25.0,
    "conical_pitch": 15.0,
    "n_batches": 200,
    "run_mode": "render"
}
```

Then, from the repository root:

```powershell
docker compose run --rm rimag python simulation_paper.py my_params.json
```

`n_batches` is still required by `simulation_paper.py`. Render mode writes the XML files and `plot.png` into `runs/default` and does not run a transport simulation.

## Plot the simulation curves

The two commands at the end of `README_paper.md` plot `scripts/materials_sim_curve.csv` and `scripts/pitch_sim_curve.csv`. Run them from the `scripts` directory. Each command takes the CSV path, the maximum moderator thickness used to extend the fitted curves (`170` cm), and the bottom of the logarithmic y-axis (`1.16e7`).

Material curves. Every series is fitted with an exponential. `--exp-fit-start` drops the first N points of that series before fitting: 3 for Graphite and BeO, 2 for Water, and 1 for HDPE, TiH2, and Li2O.

```powershell
cd scripts
python .\data_plotter.py .\materials_sim_curve.csv 170 1.16e7 --exp-fit-start "Graphite" 3 --exp-fit-start "BeO" 3 --exp-fit-start "Water" 2 --exp-fit-start "HDPE" 1 --exp-fit-start "TiH2" 1 --exp-fit-start "Li2O" 1
```

Pitch curves. The column named `0` is drawn without a fit. Every other series is fitted with an exponential that starts after the first two points (`--global-fit-start 2`).

```powershell
python .\data_plotter.py .\pitch_sim_curve.csv 170 1.16e7 --no-fit-material "0" --global-fit-start 2
```
