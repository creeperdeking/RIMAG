#!/usr/bin/env python3

import argparse
import csv
import math
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit


def is_incomplete(value: str) -> bool:
    return value.strip().lower().startswith("#todo")


def parse_float_or_nan(value: str) -> float:
    value = value.strip()
    if is_incomplete(value):
        return float("nan")
    return float(value)


def parse_percent(value: str) -> float:
    value = value.strip()
    if value.endswith("%"):
        return float(value[:-1]) / 100.0
    return float(value) / 100.0


def exponential_model(x, a, b):
    return a * np.exp(b * x)


def linear_model(x, m, b):
    return m * x + b


def read_csv_data(csv_path: Path):
    with csv_path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = [name.strip() for name in reader.fieldnames]

        x_column = fieldnames[0]

        materials = [
            name for name in fieldnames[1:]
            if not name.endswith("%")
        ]

        rows = list(reader)

    x = np.array([parse_float_or_nan(row[x_column]) for row in rows], dtype=float)

    data = {}

    for material in materials:
        percent_column = f"{material}%"

        if percent_column not in fieldnames:
            raise ValueError(f"Missing uncertainty column: {percent_column}")

        y = []
        yerr_fraction = []

        for row in rows:
            y_value = row[material]
            percent_value = row[percent_column]

            if is_incomplete(y_value) or is_incomplete(percent_value):
                y.append(float("nan"))
                yerr_fraction.append(float("nan"))
            else:
                y.append(float(y_value.strip()))
                yerr_fraction.append(parse_percent(percent_value))

        y = np.array(y, dtype=float)
        yerr_fraction = np.array(yerr_fraction, dtype=float)

        yerr = y * yerr_fraction

        data[material] = {
            "y": y,
            "yerr": yerr,
            "yerr_fraction": yerr_fraction,
        }

    return x_column, x, data


def fit_exponential(x, y, yerr, start_index=0):
    if start_index > 0:
        x = x[start_index:]
        y = y[start_index:]
        yerr = yerr[start_index:]

    valid = (
        np.isfinite(x)
        & np.isfinite(y)
        & np.isfinite(yerr)
        & (y > 0)
        & (yerr > 0)
    )

    if np.count_nonzero(valid) < 2:
        raise ValueError("Need at least two valid positive points for exponential fit.")

    x_fit = x[valid]
    y_fit = y[valid]
    yerr_fit = yerr[valid]

    slope, intercept = np.polyfit(x_fit, np.log(y_fit), 1)
    p0 = [math.exp(intercept), slope]

    popt, pcov = curve_fit(
        exponential_model,
        x_fit,
        y_fit,
        p0=p0,
        sigma=yerr_fit,
        absolute_sigma=True,
        bounds=([0.0, -np.inf], [np.inf, np.inf]),
        maxfev=10000,
    )

    return popt, pcov


def fit_linear(x, y, yerr):
    valid = (
        np.isfinite(x)
        & np.isfinite(y)
        & np.isfinite(yerr)
        & (yerr > 0)
    )

    if np.count_nonzero(valid) < 2:
        raise ValueError("Need at least two valid points for linear fit.")

    x_fit = x[valid]
    y_fit = y[valid]
    yerr_fit = yerr[valid]

    m0, b0 = np.polyfit(x_fit, y_fit, 1)

    popt, pcov = curve_fit(
        linear_model,
        x_fit,
        y_fit,
        p0=[m0, b0],
        sigma=yerr_fit,
        absolute_sigma=True,
        maxfev=10000,
    )

    return popt, pcov


def exponential_x_at_y(y_target, a, b):
    if y_target <= 0 or a <= 0:
        return None

    if b == 0:
        return None

    return math.log(y_target / a) / b


def linear_x_at_y(y_target, m, b):
    if m == 0:
        return None

    return (y_target - b) / m


def make_plot(
    csv_path: Path,
    max_thickness: float,
    min_y_axis: float,
    linear_material: str | None = None,
    no_fit_material: str | None = None,
    global_fit_start: int = 0,
    exp_fit_start: dict[str, int] | None = None,
):
    if min_y_axis <= 0:
        raise ValueError("The minimum y-axis value must be positive for a logarithmic y-axis.")

    if global_fit_start < 0:
        raise ValueError("--global-fit-start must be zero or a positive integer.")

    exp_fit_start = exp_fit_start or {}

    x_column, x, data = read_csv_data(csv_path)

    if linear_material is not None and linear_material not in data:
        available = ", ".join(data.keys())
        raise ValueError(
            f"Linear-fit material '{linear_material}' was not found in the CSV. "
            f"Available materials: {available}"
        )

    if no_fit_material is not None and no_fit_material not in data:
        available = ", ".join(data.keys())
        raise ValueError(
            f"No-fit material '{no_fit_material}' was not found in the CSV. "
            f"Available materials: {available}"
        )

    for material, start_index in exp_fit_start.items():
        if material not in data:
            available = ", ".join(data.keys())
            raise ValueError(
                f"Exp-fit-start material '{material}' was not found in the CSV. "
                f"Available materials: {available}"
            )
        if start_index < 0:
            raise ValueError(
                f"--exp-fit-start for '{material}' must be zero or a positive integer."
            )

    if (
        linear_material is not None
        and no_fit_material is not None
        and linear_material == no_fit_material
    ):
        raise ValueError(
            f"Material '{linear_material}' cannot be both --linear-material "
            f"and --no-fit-material."
        )

    x_min = np.nanmin(x)

    if max_thickness <= x_min:
        raise ValueError(
            f"Maximum moderator thickness must be greater than the minimum data thickness "
            f"({x_min})."
        )

    x_curve = np.linspace(x_min, max_thickness, 500)

    fig, ax = plt.subplots(figsize=(8, 5))

    crossing_results = []

    for material, values in data.items():
        y = values["y"]
        yerr = values["yerr"]

        errorbar_container = ax.errorbar(
            x,
            y,
            yerr=yerr,
            fmt="o",
            capsize=3,
            label=f"{material} data",
        )

        color = errorbar_container.lines[0].get_color()

        if material == no_fit_material:
            continue

        try:
            if material == linear_material:
                popt, _ = fit_linear(x, y, yerr)
                m, b = popt

                y_curve = linear_model(x_curve, m, b)

                # On a log y-axis, non-positive values cannot be shown.
                y_curve = np.where(y_curve > 0, y_curve, np.nan)

                ax.plot(
                    x_curve,
                    y_curve,
                    linestyle="--",
                    color=color,
                    label=f"{material} linear fit",
                )

                x_cross = linear_x_at_y(min_y_axis, m, b)

                crossing_results.append(
                    {
                        "material": material,
                        "fit_type": "linear",
                        "parameters": f"m = {m:.6e}, b = {b:.6e}",
                        "x_cross": x_cross,
                    }
                )

            else:
                start_index = exp_fit_start.get(material, global_fit_start)
                popt, _ = fit_exponential(x, y, yerr, start_index=start_index)
                a, b = popt

                y_curve = exponential_model(x_curve, a, b)

                ax.plot(
                    x_curve,
                    y_curve,
                    linestyle="--",
                    color=color,
                    label=f"{material} exp. fit",
                )

                x_cross = exponential_x_at_y(min_y_axis, a, b)

                crossing_results.append(
                    {
                        "material": material,
                        "fit_type": "exponential",
                        "parameters": f"a = {a:.6e}, b = {b:.6e}",
                        "x_cross": x_cross,
                    }
                )

        except ValueError as exc:
            print(f"Skipping fit for {material}: {exc}")

    ax.set_xlabel(x_column)
    ax.set_ylabel("neutron Displacement Damage Dose (MeV/g)")

    ax.set_yscale("log")
    ax.set_xlim(x_min, max_thickness)
    ax.set_ylim(bottom=min_y_axis)

    ax.grid(True, which="both", linewidth=0.5)
    ax.legend(frameon=False, fontsize=8)

    fig.tight_layout()

    print()
    print(f"Fitted-curve crossings at y = {min_y_axis:.6e}")
    print("-" * 72)

    for result in crossing_results:
        material = result["material"]
        fit_type = result["fit_type"]
        parameters = result["parameters"]
        x_cross = result["x_cross"]

        if x_cross is None or not np.isfinite(x_cross):
            print(f"{material}: {fit_type} fit has no unique crossing. {parameters}")
        else:
            print(
                f"{material}: {fit_type} fit crosses y = {min_y_axis:.6e} "
                f"at {x_column} = {x_cross:.6g}. {parameters}"
            )

    if no_fit_material is not None:
        print(f"{no_fit_material}: no fit requested.")

    print()

    plt.show()


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Plot moderator CSV data with pointwise percentage error bars. "
            "By default, all materials receive exponential fits. Optionally, "
            "one material can receive a linear fit, and one material can receive no fit."
        )
    )

    parser.add_argument(
        "csv_file",
        type=Path,
        help="Input CSV file.",
    )

    parser.add_argument(
        "max_thickness",
        type=float,
        help="Maximum moderator thickness to extrapolate and plot to.",
    )

    parser.add_argument(
        "min_y_axis",
        type=float,
        help="Minimum y-axis value. Must be positive because the y-axis is logarithmic.",
    )

    parser.add_argument(
        "--linear-material",
        type=str,
        default=None,
        help=(
            "Name of one material to fit linearly instead of exponentially, "
            "for example: HDPE. If omitted, all fitted materials use exponential fits."
        ),
    )

    parser.add_argument(
        "--no-fit-material",
        type=str,
        default=None,
        help=(
            "Name of one material for which no fit curve should be drawn, "
            "for example: Graphite. The data points and error bars are still shown."
        ),
    )

    parser.add_argument(
        "--global-fit-start",
        type=int,
        default=0,
        help=(
            "Number of initial data points to exclude from all exponential fits. "
            "For example, 1 uses only points after the first for every material. "
            "Per-material --exp-fit-start values override this default."
        ),
    )

    parser.add_argument(
        "--exp-fit-start",
        nargs=2,
        metavar=("MATERIAL", "START"),
        action="append",
        default=[],
        help=(
            "Per-material start index for exponential fits. Can be repeated. "
            "For example, --exp-fit-start Graphite 1 fits Graphite using only "
            "points after the first. Materials without this option use "
            "--global-fit-start."
        ),
    )

    args = parser.parse_args()

    exp_fit_start: dict[str, int] = {}
    for material, start_str in args.exp_fit_start:
        if material in exp_fit_start:
            raise ValueError(
                f"--exp-fit-start was specified more than once for '{material}'."
            )
        try:
            start_index = int(start_str)
        except ValueError as exc:
            raise ValueError(
                f"--exp-fit-start start index for '{material}' must be an integer."
            ) from exc
        exp_fit_start[material] = start_index

    make_plot(
        args.csv_file,
        args.max_thickness,
        args.min_y_axis,
        args.linear_material,
        args.no_fit_material,
        args.global_fit_start,
        exp_fit_start,
    )


if __name__ == "__main__":
    main()