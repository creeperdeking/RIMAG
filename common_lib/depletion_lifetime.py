"""Step size and keff-crossing math for a fuel-lifetime depletion.

OpenMC integrates whatever timesteps it is given. This module decides those
timesteps and, once the series exists, the time and burnup where the mean
keff falls through 1. It does not import OpenMC.
"""

from __future__ import annotations

from dataclasses import dataclass

# Short steps so Xe-135 can build in before the long burns.
XENON_STEPS_DAYS = (0.01, 0.1, 0.89, 1.0)
MAX_DAYS = 40.0 * 365.0
MAX_STEPS = 500


@dataclass(frozen=True)
class DepletionCrossing:
    below_one: bool
    years: float
    days: float
    burnup_mwd_per_kg: float
    keff: float
    keff_uncertainty: float


def burnup_mwd_per_kg(thermal_power_w: float, time_days: float, fuel_mass_kg: float) -> float:
    """MWd/kgHM at constant thermal power. ``fuel_mass_kg`` is heavy metal."""
    if fuel_mass_kg <= 0.0:
        return float("nan")
    return (thermal_power_w / 1.0e6) * time_days / fuel_mass_kg


def max_step_days(heavy_metal_g: float, thermal_power_w: float) -> float:
    """Days that deposit about 2 MWd/kgHM. OpenMC's heavy-metal mass is grams."""
    if thermal_power_w <= 0.0 or heavy_metal_g <= 0.0:
        return 30.0
    return 2.0 * heavy_metal_g / thermal_power_w * 1.0e3


def next_step_days(keff: float, elapsed_days: float, max_days: float = MAX_DAYS) -> float | None:
    """Next depletion step, in days, while the latest mean keff is still at least 1."""
    if keff < 1.0 or elapsed_days >= max_days - 1.0e-9:
        return None
    if keff > 1.05:
        target = 365.0
    elif keff > 1.02:
        target = 90.0
    elif keff > 1.005:
        target = 30.0
    else:
        target = 10.0
    step = min(target, max_days - elapsed_days)
    if step < 1.0:
        return None
    return step


def find_crossing(
    times_days: list[float],
    keff: list[float],
    keff_uncertainty: list[float],
    thermal_power_w: float,
    fuel_mass_kg: float,
) -> DepletionCrossing:
    """Time and burnup where the mean keff stays below 1.

    A dip that recovers (xenon, then a climb back) is not the end of life.
    The reported crossing is the last one that leaves keff below 1 through
    the end of the series. Time and burnup are linear in keff between the
    bracketing steps. The reported keff is the first simulated point below 1
    on that crossing.
    """
    if not times_days or len(times_days) != len(keff) or len(keff) != len(keff_uncertainty):
        raise ValueError("depletion series lengths do not match")

    def at(index: int, days: float, below: bool) -> DepletionCrossing:
        return DepletionCrossing(
            below_one=below,
            years=days / 365.0,
            days=days,
            burnup_mwd_per_kg=burnup_mwd_per_kg(thermal_power_w, days, fuel_mass_kg),
            keff=keff[index],
            keff_uncertainty=keff_uncertainty[index],
        )

    if keff[0] < 1.0:
        return at(0, 0.0, True)
    if keff[-1] >= 1.0:
        return at(len(keff) - 1, times_days[-1], False)

    index = len(keff) - 1
    while index > 0 and keff[index] < 1.0 and keff[index - 1] < 1.0:
        index -= 1
    if index == 0 or keff[index - 1] < 1.0:
        return at(index, times_days[index], True)

    k0 = keff[index - 1]
    k1 = keff[index]
    span = k1 - k0
    fraction = 0.0 if span == 0.0 else (1.0 - k0) / span
    fraction = min(1.0, max(0.0, fraction))
    days = times_days[index - 1] + fraction * (times_days[index] - times_days[index - 1])
    return at(index, days, True)


def format_depletion_line(crossing: DepletionCrossing) -> str:
    years = f"{crossing.years:.6g}"
    days = f"{crossing.days:.6g}"
    burnup = f"{crossing.burnup_mwd_per_kg:.6g}"
    keff = f"{crossing.keff:.5f}"
    uncertainty = f"{crossing.keff_uncertainty:.5f}"
    if crossing.below_one:
        return (
            f"Fuel depletion: keff crosses 1 at {years} years ({days} d), "
            f"burnup {burnup} MWd/kgHM. First step below 1 has keff {keff} +/- {uncertainty}"
        )
    return (
        f"Fuel depletion: keff stayed at or above 1 through {years} years ({days} d), "
        f"burnup {burnup} MWd/kgHM (keff {keff} +/- {uncertainty})"
    )


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def _self_check() -> None:
    power = 1.0e6
    mass = 2.0
    # 1 MW, 2 kg: 10 days is 5 MWd/kgHM.
    _check(abs(burnup_mwd_per_kg(power, 10.0, mass) - 5.0) < 1e-9, "burnup")
    # 2 kg = 2000 g at 1 MW -> 4 days for 2 MWd/kgHM.
    _check(abs(max_step_days(2000.0, power) - 4.0) < 1e-9, "max step")
    _check(next_step_days(1.1, 0.0) == 365.0, "far step")
    _check(next_step_days(1.03, 0.0) == 90.0, "mid step")
    _check(next_step_days(1.01, 0.0) == 30.0, "near step")
    _check(next_step_days(1.001, 0.0) == 10.0, "close step")
    _check(next_step_days(0.99, 0.0) is None, "already below")
    _check(next_step_days(1.2, MAX_DAYS) is None, "calendar cap")

    times = [0.0, 10.0, 20.0]
    keff = [1.10, 1.05, 0.90]
    unc = [0.001, 0.001, 0.002]
    crossing = find_crossing(times, keff, unc, power, mass)
    # (1-1.05)/(0.90-1.05) = 1/3 of the way from day 10 to day 20.
    _check(crossing.below_one, "should cross")
    _check(abs(crossing.days - (10.0 + 10.0 / 3.0)) < 1e-9, f"days {crossing.days}")
    _check(abs(crossing.keff - 0.90) < 1e-12, "bracket keff")
    _check(abs(crossing.burnup_mwd_per_kg - burnup_mwd_per_kg(power, crossing.days, mass)) < 1e-9, "crossing burnup")

    recovered = find_crossing([0.0, 1.0, 30.0], [1.02, 0.99, 1.01], [0.001, 0.001, 0.001], power, mass)
    _check(not recovered.below_one and abs(recovered.days - 30.0) < 1e-12, "recovered dip is not end of life")

    fresh = find_crossing([0.0, 1.0], [0.98, 0.97], [0.001, 0.001], power, mass)
    _check(fresh.below_one and fresh.days == 0.0 and abs(fresh.burnup_mwd_per_kg) < 1e-12, "already subcritical")

    line = format_depletion_line(crossing)
    _check(line.startswith("Fuel depletion: keff crosses 1 at "), line)
    _check("MWd/kgHM" in line and "+/-" in line, line)
    stayed = format_depletion_line(recovered)
    _check("stayed at or above 1" in stayed, stayed)
    print("depletion lifetime checks passed")
    print(line)


if __name__ == "__main__":
    _self_check()
