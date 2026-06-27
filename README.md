# RIMAEL

## Viewing raw results used in the paper

Using LibreOffice, open "simulation_data_paper.ods"
On the first page you will find some general informations about the simulation, and the results will be on the second and third page.

## Reproducing paper results

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

### Build & Run:

- Using LibreOffice, open "simulation_data.ods" to find which simulation you want to do. "simulation_data.ods" is a blank version of "simulation_data_paper.ods" that can be used to reproduce its results. Only the number of batches are pre-filled for each simulations, the other fields are marked "#todo".

Once you have found the table and column corresponding to the simulation you want to run, look above the table at the field named "Sim file name", and figure out the name corresponding to your simulation and the NSM thickness corresponding to the column you want to fill. 

- Start the simulation:

First, you need to build the simulation by typing:
```bash
docker compose build
```
Now you can run the simulation, you need to replace in the following command line SIM_NAME with the variant of "Sim file name" you chose previously, as well as BATCHES, you should set the number corresponding to your chosen column if you want to reproduce the result accurately.
```bash
docker compose run --rm rimag python start_sim.py "simulation_data.ods" SIM_NAME BATCHES --run-mode keff
```

- After the simulation is completed, the results are written inside a copy of "simulation_data.ods" created in the subfolder "runs/default/simulation_data.ods" in the relevant table column.