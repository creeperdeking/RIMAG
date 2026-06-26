# RIMAEL

## Reproducing paper results

Modify "threads" in simsettings.json with the number relevant for your machine:

Build:
- go the the relevant branch (for reproducing the paper's result, do git checkout research_paper)
- Using LibreOffice, open "Simulation data.ods" to find which simulation you want to do
- Start the simulation
```bash
docker compose build
docker compose run --rm rimag python start_sim.py "Simulation data.ods" [sim file name from the ods file, for example "simpaper_1_0.5.json"] [number of batches, for example 50] --run-mode keff
```
- This simulation result is written inside "Simulation data.ods" in the relevant table column (you may have to close and re-open the file in LibreOffice to see the change)