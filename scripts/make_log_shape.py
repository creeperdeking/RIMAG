#!/usr/bin/env python3
"""
Headless-safe rotating logarithmic surface plotter with true-scale axes.

This version avoids Qt entirely by forcing Matplotlib's non-GUI Agg backend.
It saves plots to image files instead of opening GUI windows.

Shape:
    z(r) = R tan(beta) ln(R / r)

where beta is the local tangent angle below horizontal at outer radius R.

Required angular speed:
    omega = sqrt(g / (R tan(beta)))

Use:
    python scripts/make_log_shape.py --outer-radius 2 --angle 2 --inner-radius 0.8
"""

from __future__ import annotations

import argparse
import os

# Force non-GUI backend before importing pyplot.
os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib

matplotlib.use("Agg", force=True)

import numpy as np
import matplotlib.pyplot as plt


def rotating_log_shape(
    outer_radius_m: float,
    angle_deg: float,
    inner_radius_m: float,
    n_points: int,
    g: float,
):
    if outer_radius_m <= 0:
        raise ValueError("outer_radius_m must be positive.")

    if not (0.0 < angle_deg < 90.0):
        raise ValueError("angle_deg must be between 0 and 90 degrees.")

    if inner_radius_m <= 0:
        raise ValueError(
            "inner_radius_m must be positive; the ideal logarithmic shape is singular at r = 0."
        )

    if inner_radius_m >= outer_radius_m:
        raise ValueError("inner_radius_m must be smaller than outer_radius_m.")

    if n_points < 2:
        raise ValueError("n_points must be at least 2.")

    if g <= 0:
        raise ValueError("g must be positive.")

    beta_rad = np.deg2rad(angle_deg)

    height_scale_m = outer_radius_m * np.tan(beta_rad)

    omega_rad_s = np.sqrt(g / height_scale_m)
    frequency_hz = omega_rad_s / (2.0 * np.pi)
    rpm = 60.0 * frequency_hz

    r = np.linspace(inner_radius_m, outer_radius_m, n_points)

    # Define z = 0 at the outer rim.
    z = height_scale_m * np.log(outer_radius_m / r)

    return r, z, omega_rad_s, frequency_hz, rpm, height_scale_m


def set_equal_2d_limits(ax, x_min, x_max, y_min, y_max, margin_fraction=0.05):
    """
    Set 2D axis limits so that one plotted metre in x equals one plotted metre in y.
    This prevents visual distortion of the logarithmic slope.
    """

    x_center = 0.5 * (x_min + x_max)
    y_center = 0.5 * (y_min + y_max)

    x_range = x_max - x_min
    y_range = y_max - y_min

    max_range = max(x_range, y_range)

    if max_range <= 0:
        max_range = 1.0

    max_range *= 1.0 + margin_fraction

    half_range = 0.5 * max_range

    ax.set_xlim(x_center - half_range, x_center + half_range)
    ax.set_ylim(y_center - half_range, y_center + half_range)
    ax.set_aspect("equal", adjustable="box")


def set_equal_3d_axes(ax, x, y, z, margin_fraction=0.05):
    """
    Set 3D axis limits and box aspect so x, y, and z are shown at the same scale.
    """

    x_min, x_max = float(np.min(x)), float(np.max(x))
    y_min, y_max = float(np.min(y)), float(np.max(y))
    z_min, z_max = float(np.min(z)), float(np.max(z))

    x_center = 0.5 * (x_min + x_max)
    y_center = 0.5 * (y_min + y_max)
    z_center = 0.5 * (z_min + z_max)

    x_range = x_max - x_min
    y_range = y_max - y_min
    z_range = z_max - z_min

    max_range = max(x_range, y_range, z_range)

    if max_range <= 0:
        max_range = 1.0

    max_range *= 1.0 + margin_fraction

    half_range = 0.5 * max_range

    ax.set_xlim(x_center - half_range, x_center + half_range)
    ax.set_ylim(y_center - half_range, y_center + half_range)
    ax.set_zlim(z_center - half_range, z_center + half_range)

    # True equal scale in 3D.
    ax.set_box_aspect((1.0, 1.0, 1.0))


def save_2d_profile(
    r,
    z,
    output_path: str,
    outer_radius_m: float,
    inner_radius_m: float,
    angle_deg: float,
    omega_rad_s: float,
    rpm: float,
    dpi: int,
):
    fig, ax = plt.subplots(figsize=(8.0, 8.0))

    # Plot both sides of the axisymmetric cross-section.
    x_right = r
    x_left = -r

    ax.plot(x_right, z, label="surface profile")
    ax.plot(x_left, z)

    ax.axhline(0.0, linewidth=0.8)
    ax.axvline(0.0, linewidth=0.8)

    x_min = -outer_radius_m
    x_max = outer_radius_m
    y_min = 0.0
    y_max = float(np.max(z))

    set_equal_2d_limits(ax, x_min, x_max, y_min, y_max)

    ax.set_xlabel("radius r [m]")
    ax.set_ylabel("height z [m]")
    ax.set_title(
        "Rotating logarithmic surface, true-scale cross-section\n"
        f"R = {outer_radius_m:.4g} m, "
        f"r_inner = {inner_radius_m:.4g} m, "
        f"angle = {angle_deg:.4g}°, "
        f"ω = {omega_rad_s:.4g} rad/s = {rpm:.4g} rpm"
    )

    ax.grid(True)
    ax.legend()

    fig.tight_layout()
    fig.savefig(output_path, dpi=dpi)
    plt.close(fig)


def save_3d_surface(
    r,
    z,
    output_path: str,
    dpi: int,
    theta_points: int,
):
    theta = np.linspace(0.0, 2.0 * np.pi, theta_points)
    R_grid, Theta_grid = np.meshgrid(r, theta)

    X_grid = R_grid * np.cos(Theta_grid)
    Y_grid = R_grid * np.sin(Theta_grid)
    Z_grid = np.tile(z, (theta.size, 1))

    fig = plt.figure(figsize=(8.0, 8.0))
    ax = fig.add_subplot(111, projection="3d")

    ax.plot_surface(
        X_grid,
        Y_grid,
        Z_grid,
        linewidth=0,
        antialiased=True,
        alpha=0.9,
    )

    set_equal_3d_axes(ax, X_grid, Y_grid, Z_grid)

    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.set_zlabel("z [m]")
    ax.set_title("3D rotating logarithmic surface, true-scale axes")

    fig.tight_layout()
    fig.savefig(output_path, dpi=dpi)
    plt.close(fig)


def save_csv(path: str, r, z):
    data = np.column_stack((r, z))
    np.savetxt(
        path,
        data,
        delimiter=",",
        header="r_m,z_m",
        comments="",
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Compute and save true-scale plots of the rotating logarithmic zero-normal-force surface."
    )

    parser.add_argument(
        "-R",
        "--outer-radius",
        type=float,
        required=True,
        help="Outer radius in m.",
    )

    parser.add_argument(
        "-a",
        "--angle",
        type=float,
        required=True,
        help="Local tangent angle below horizontal at the outer radius, in degrees.",
    )

    parser.add_argument(
        "-r",
        "--inner-radius",
        type=float,
        default=None,
        help="Inner cutoff radius in m. Default: 1%% of outer radius.",
    )

    parser.add_argument(
        "-n",
        "--points",
        type=int,
        default=500,
        help="Number of radial points. Default: 500.",
    )

    parser.add_argument(
        "--g",
        type=float,
        default=9.80665,
        help="Gravitational acceleration in m/s^2. Default: 9.80665.",
    )

    parser.add_argument(
        "--save-2d",
        type=str,
        default="rotating_shape_2d_true_scale.png",
        help="2D output image path. Default: rotating_shape_2d_true_scale.png.",
    )

    parser.add_argument(
        "--save-3d",
        type=str,
        default="rotating_shape_3d_true_scale.png",
        help="3D output image path. Default: rotating_shape_3d_true_scale.png.",
    )

    parser.add_argument(
        "--no-3d",
        action="store_true",
        help="Skip the 3D surface plot.",
    )

    parser.add_argument(
        "--csv",
        type=str,
        default=None,
        help="Optional CSV output path for r,z profile data.",
    )

    parser.add_argument(
        "--dpi",
        type=int,
        default=160,
        help="Image DPI. Default: 160.",
    )

    parser.add_argument(
        "--theta-points",
        type=int,
        default=240,
        help="Number of angular points for the 3D surface. Default: 240.",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    inner_radius_m = args.inner_radius
    if inner_radius_m is None:
        inner_radius_m = 0.01 * args.outer_radius

    r, z, omega_rad_s, frequency_hz, rpm, height_scale_m = rotating_log_shape(
        outer_radius_m=args.outer_radius,
        angle_deg=args.angle,
        inner_radius_m=inner_radius_m,
        n_points=args.points,
        g=args.g,
    )

    print("Rotating logarithmic surface")
    print("--------------------------------")
    print(f"Outer radius:              {args.outer_radius:.8g} m")
    print(f"Inner cutoff radius:       {inner_radius_m:.8g} m")
    print(f"Outer tangent angle:       {args.angle:.8g} deg below horizontal")
    print(f"g:                         {args.g:.8g} m/s^2")
    print(f"Height scale R tan(angle): {height_scale_m:.8g} m")
    print(f"Angular speed omega:       {omega_rad_s:.8g} rad/s")
    print(f"Frequency:                 {frequency_hz:.8g} Hz")
    print(f"Rotation speed:            {rpm:.8g} rpm")
    print(f"Height at inner cutoff:    {z[0]:.8g} m above outer rim")
    print(f"Height at outer radius:    {z[-1]:.8g} m")

    save_2d_profile(
        r=r,
        z=z,
        output_path=args.save_2d,
        outer_radius_m=args.outer_radius,
        inner_radius_m=inner_radius_m,
        angle_deg=args.angle,
        omega_rad_s=omega_rad_s,
        rpm=rpm,
        dpi=args.dpi,
    )

    print(f"Saved true-scale 2D plot:  {args.save_2d}")

    if not args.no_3d:
        save_3d_surface(
            r=r,
            z=z,
            output_path=args.save_3d,
            dpi=args.dpi,
            theta_points=args.theta_points,
        )
        print(f"Saved true-scale 3D plot:  {args.save_3d}")

    if args.csv:
        save_csv(args.csv, r, z)
        print(f"Saved CSV profile:         {args.csv}")


if __name__ == "__main__":
    main()