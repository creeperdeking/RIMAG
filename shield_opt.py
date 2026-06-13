#!/usr/bin/env python3
"""
Usage:
python shield_opt.py \
  --moderator-name polyethylene \
  --moderator-density 950 \
  --xi 0.8 \
  --sigma-s 25 \
  --e0 2e6 \
  --reduction-orders 10

Moderator thickness:             0.55 m
B4C thickness:                   0.10 m
Total thickness:                 0.65 m
Neutron energy after moderator:  ~34 eV

Toy two-stage neutron shield optimizer:

    Moderator layer:
        E(x) = E0 * exp(-beta * x)
        beta = xi_bar * Sigma_s

    B4C absorber layer:
        Sigma_a(E) = Sigma_a_th * sqrt(E_th / E)

    Required attenuation:
        Phi_out / Phi_in = 1 / reduction_factor

    Minimize:
        T(x) = x + y(x)

where:
    x = moderator thickness [m]
    y = B4C thickness [m]

This is a simple straight-ahead continuous-slowing-down model.
It is NOT a replacement for neutron transport calculation.
"""

from dataclasses import dataclass
from math import exp, log, sqrt
import argparse


AVOGADRO = 6.02214076e23  # 1/mol
BARN = 1.0e-28            # m^2


@dataclass
class Moderator:
    name: str
    density_kg_m3: float
    xi_bar: float
    sigma_s_macro_1_m: float

    @property
    def beta_1_m(self) -> float:
        """
        Continuous slowing-down coefficient:
            beta = xi_bar * Sigma_s
        """
        return self.xi_bar * self.sigma_s_macro_1_m


@dataclass
class B4C:
    density_kg_m3: float = 2520.0
    boron_atomic_mass_g_mol: float = 10.81
    carbon_atomic_mass_g_mol: float = 12.011
    b10_atom_fraction: float = 0.199
    sigma_a_b10_thermal_barns: float = 3837.0
    thermal_energy_eV: float = 0.0253

    @property
    def molar_mass_kg_mol(self) -> float:
        """
        Natural B4C molar mass:
            M = 4 M_B + M_C
        """
        molar_mass_g_mol = 4.0 * self.boron_atomic_mass_g_mol + self.carbon_atomic_mass_g_mol
        return molar_mass_g_mol / 1000.0

    @property
    def molecule_number_density_1_m3(self) -> float:
        return self.density_kg_m3 / self.molar_mass_kg_mol * AVOGADRO

    @property
    def b10_number_density_1_m3(self) -> float:
        """
        Each B4C molecule has 4 boron atoms.
        """
        return 4.0 * self.molecule_number_density_1_m3 * self.b10_atom_fraction

    @property
    def sigma_a_b10_thermal_m2(self) -> float:
        return self.sigma_a_b10_thermal_barns * BARN

    @property
    def sigma_a_macro_thermal_1_m(self) -> float:
        """
        Thermal macroscopic absorption coefficient of B4C.
        """
        return self.b10_number_density_1_m3 * self.sigma_a_b10_thermal_m2

    def sigma_a_macro_at_energy(self, energy_eV: float) -> float:
        """
        1/v absorption approximation:
            Sigma_a(E) = Sigma_a_th * sqrt(E_th / E)
        """
        if energy_eV <= 0.0:
            raise ValueError("Neutron energy must be positive.")
        return self.sigma_a_macro_thermal_1_m * sqrt(self.thermal_energy_eV / energy_eV)


@dataclass
class ShieldResult:
    moderator_thickness_m: float
    b4c_thickness_m: float
    total_thickness_m: float
    neutron_energy_after_moderator_eV: float
    b4c_macro_absorption_1_m: float
    optical_depth: float
    achieved_reduction_factor: float


def optimize_two_layer_shield(
    moderator: Moderator,
    reduction_factor: float,
    initial_energy_eV: float,
    absorber: B4C = B4C(),
) -> ShieldResult:
    """
    Finds the moderator and B4C thicknesses that minimize total thickness
    under the toy two-stage model.

    Derivation:

        E(x) = E0 exp(-beta x)

        Sigma_a(x) = Sigma_a_th sqrt(E_th / E(x))
                   = Sigma_a_th sqrt(E_th / E0) exp(beta x / 2)

        Required absorber thickness:
            y(x) = G / Sigma_a(x)

        where:
            G = ln(reduction_factor)

        Therefore:
            y(x) = K exp(-beta x / 2)

        with:
            K = G / Sigma_a_th * sqrt(E0 / E_th)

        Minimize:
            T(x) = x + K exp(-beta x / 2)

        Interior optimum:
            dT/dx = 0

            y* = 2 / beta

            x* = 2 / beta * ln(beta K / 2)

        If beta K / 2 <= 1, the mathematical optimum is x = 0.
    """

    if reduction_factor <= 1.0:
        raise ValueError("reduction_factor must be greater than 1.")

    if initial_energy_eV <= 0.0:
        raise ValueError("initial_energy_eV must be positive.")

    beta = moderator.beta_1_m

    if beta <= 0.0:
        raise ValueError("Moderator beta = xi_bar * Sigma_s must be positive.")

    sigma_a_th = absorber.sigma_a_macro_thermal_1_m

    if sigma_a_th <= 0.0:
        raise ValueError("B4C thermal macroscopic absorption coefficient must be positive.")

    G = log(reduction_factor)

    K = G / sigma_a_th * sqrt(initial_energy_eV / absorber.thermal_energy_eV)

    dimensionless_optimum_parameter = beta * K / 2.0

    if dimensionless_optimum_parameter <= 1.0:
        # Boundary optimum: no moderator.
        x = 0.0
        y = K
    else:
        # Interior optimum.
        x = 2.0 / beta * log(dimensionless_optimum_parameter)
        y = 2.0 / beta

    energy_after_moderator = initial_energy_eV * exp(-beta * x)
    sigma_a_at_exit_energy = absorber.sigma_a_macro_at_energy(energy_after_moderator)

    optical_depth = sigma_a_at_exit_energy * y
    achieved_reduction_factor = exp(optical_depth)

    return ShieldResult(
        moderator_thickness_m=x,
        b4c_thickness_m=y,
        total_thickness_m=x + y,
        neutron_energy_after_moderator_eV=energy_after_moderator,
        b4c_macro_absorption_1_m=sigma_a_at_exit_energy,
        optical_depth=optical_depth,
        achieved_reduction_factor=achieved_reduction_factor,
    )


def print_result(
    moderator: Moderator,
    absorber: B4C,
    result: ShieldResult,
    reduction_factor: float,
    initial_energy_eV: float,
) -> None:
    print()
    print("Toy two-layer neutron shield optimization")
    print("----------------------------------------")
    print(f"Moderator material:              {moderator.name}")
    print(f"Moderator density:               {moderator.density_kg_m3:.6g} kg/m^3")
    print(f"Average log energy decrement:    {moderator.xi_bar:.6g}")
    print(f"Macroscopic scattering coeff.:   {moderator.sigma_s_macro_1_m:.6g} 1/m")
    print(f"Slowing-down beta:               {moderator.beta_1_m:.6g} 1/m")
    print()
    print("B4C absorber assumptions")
    print("------------------------")
    print(f"B4C density:                     {absorber.density_kg_m3:.6g} kg/m^3")
    print(f"B-10 atom fraction in boron:     {absorber.b10_atom_fraction:.6g}")
    print(f"B-10 thermal absorption xs:      {absorber.sigma_a_b10_thermal_barns:.6g} barns")
    print(f"B4C thermal Sigma_a:             {absorber.sigma_a_macro_thermal_1_m:.6g} 1/m")
    print(f"Thermal reference energy:        {absorber.thermal_energy_eV:.6g} eV")
    print()
    print("Problem")
    print("-------")
    print(f"Initial neutron energy:          {initial_energy_eV:.6g} eV")
    print(f"Required reduction factor:       {reduction_factor:.6g}")
    print(f"Required optical depth:          {log(reduction_factor):.6g}")
    print()
    print("Optimized thicknesses")
    print("---------------------")
    print(f"Moderator thickness:             {result.moderator_thickness_m:.6g} m")
    print(f"B4C thickness:                   {result.b4c_thickness_m:.6g} m")
    print(f"Total thickness:                 {result.total_thickness_m:.6g} m")
    print()
    print("State at B4C entrance")
    print("---------------------")
    print(f"Neutron energy after moderator:  {result.neutron_energy_after_moderator_eV:.6g} eV")
    print(f"B4C Sigma_a at that energy:      {result.b4c_macro_absorption_1_m:.6g} 1/m")
    print()
    print("Check")
    print("-----")
    print(f"Absorber optical depth:          {result.optical_depth:.6g}")
    print(f"Achieved reduction factor:       {result.achieved_reduction_factor:.6g}")
    print(f"Achieved flux fraction:          {1.0 / result.achieved_reduction_factor:.6g}")
    print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Optimize a moderator + B4C neutron shield using a toy two-stage model."
    )

    parser.add_argument("--moderator-name", default="polyethylene")
    parser.add_argument("--moderator-density", type=float, required=True, help="kg/m^3")
    parser.add_argument("--xi", type=float, required=True, help="average logarithmic energy decrement per collision")
    parser.add_argument("--sigma-s", type=float, required=True, help="effective macroscopic scattering coefficient, 1/m")
    parser.add_argument("--e0", type=float, required=True, help="initial neutron energy, eV")

    reduction_group = parser.add_mutually_exclusive_group(required=True)
    reduction_group.add_argument("--reduction-factor", type=float, help="e.g. 1e10")
    reduction_group.add_argument("--reduction-orders", type=float, help="e.g. 10 for ten orders of magnitude")

    parser.add_argument("--b4c-density", type=float, default=2520.0, help="kg/m^3")
    parser.add_argument("--b10-fraction", type=float, default=0.199, help="B-10 atom fraction in boron")
    parser.add_argument("--b10-sigma-thermal", type=float, default=3837.0, help="B-10 thermal absorption xs, barns")
    parser.add_argument("--thermal-energy", type=float, default=0.0253, help="thermal reference energy, eV")

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.reduction_factor is not None:
        reduction_factor = args.reduction_factor
    else:
        reduction_factor = 10.0 ** args.reduction_orders

    moderator = Moderator(
        name=args.moderator_name,
        density_kg_m3=args.moderator_density,
        xi_bar=args.xi,
        sigma_s_macro_1_m=args.sigma_s,
    )

    absorber = B4C(
        density_kg_m3=args.b4c_density,
        b10_atom_fraction=args.b10_fraction,
        sigma_a_b10_thermal_barns=args.b10_sigma_thermal,
        thermal_energy_eV=args.thermal_energy,
    )

    result = optimize_two_layer_shield(
        moderator=moderator,
        reduction_factor=reduction_factor,
        initial_energy_eV=args.e0,
        absorber=absorber,
    )

    print_result(
        moderator=moderator,
        absorber=absorber,
        result=result,
        reduction_factor=reduction_factor,
        initial_energy_eV=args.e0,
    )


if __name__ == "__main__":
    main()