# RIMAEL

## Reproducing paper results

Install Docker on your machine https://www.docker.com/products/docker-desktop/

Download and extract cross sections data for ENDF/B-VIII.0 from https://openmc.org/data/

In this project modify the ".env" file to set:
- OPENMC_DATA_DIR to your cross section data folder that contains cross_sections.xml
- THREADS to the number relevant for your machine, for example if you have 20 logical cpu cores set "threads" as 20.

Build:
- Go the the relevant git branch:
``` bash
git checkout research_paper
```
- Using LibreOffice, open "Simulation data.ods" to find which simulation you want to do
- Start the simulation
```bash
docker compose build
docker compose run --rm rimag python start_sim.py "Simulation data.ods" [sim file name from the ods file, for example "simpaper_1_0.5.json"] [number of batches, for example 50] --run-mode keff
```
- After the simulation is completed, the simulation result is written inside "Simulation data.ods" in the relevant table column (you may have to close and re-open the file in LibreOffice to see the change)