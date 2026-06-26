import re
import sys
from pathlib import Path

def polyethylene_volume_dm3_per_kw(filename: str) -> float:
    total_mass = 0.0
    polyethylene_density = 0.96  # kg/dm^3

    pattern = re.compile(
        r"^'(?P<name>[^']*)'\s*:\s*mass per kW\s*=\s*(?P<value>[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*kg/kW",
        re.IGNORECASE,
    )

    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            match = pattern.search(line.strip())
            if not match:
                continue

            material_name = match.group("name").lower()
            mass_per_kw = float(match.group("value"))

            if "polyethylene" in material_name:
                total_mass += mass_per_kw

    volume_dm3_per_kw = total_mass / polyethylene_density
    return volume_dm3_per_kw


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {Path(sys.argv[0]).name} input.txt")
        sys.exit(1)

    volume = polyethylene_volume_dm3_per_kw(sys.argv[1])
    print(f"Volume in dm3 per kW = {volume:.2f}")