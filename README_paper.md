# RIMAEL

## Viewing raw results used in the paper

Using LibreOffice, open "simulation_data_paper.ods"
On the first page you will find some general informations about the simulation, and the results will be on the second and third page.

## Reproducing paper results

The spreadsheet runner and `simulation_paper.py` have been removed from this branch. The ODS files keep the recorded paper results. To reproduce those runs, check out the `research_paper` branch. New transport runs are queued from the app and executed by `simulation_app_slice.py`.

### Prerequisites

Install Docker on your machine [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/)

Download and extract cross sections data for ENDF/B-VIII.0 from [https://openmc.org/data/](https://openmc.org/data/) somewhere

### Setting up repository
Go the the relevant git branch:
``` bash
git checkout research_paper
```

In this project modify the ".env" file to set:
- OPENMC_DATA_DIR to the path of your cross section data folder that contains cross_sections.xml. If you are on windows use "/" instead of "\" when writing up the path.
- THREADS to the number relevant for your machine, for example if you have 20 logical cpu cores set "threads" as 20.

python .\data_plotter.py .\materials_sim_curve.csv 170 1.16e7  --exp-fit-start "Graphite" 3 --exp-fit-start "BeO" 3 --exp-fit-start "Water" 2 --exp-fit-start "HDPE" 1 --exp-fit-start "TiH2" 1 --exp-fit-start "Li2O" 1

python .\data_plotter.py .\pitch_sim_curve.csv 170 1.16e7  --no-fit-material "0" --global-fit-start 2
