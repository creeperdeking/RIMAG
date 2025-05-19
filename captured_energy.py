from scipy.constants import h, c, k
from scipy.integrate import quad
import numpy as np

# Constants
T_Celsius = 1200
T_Kelvin = T_Celsius + 273.15


# Planck's law for spectral radiance (per wavelength)
def planck_lambda(wavelength, T):
    return (
        (2 * h * c**2)
        / (wavelength**5)
        * (1 / (np.exp(h * c / (wavelength * k * T)) - 1))
    )


# Integrate Planck's law from 0 to 800 nm and from 0 to infinity
lambda_limit = 800e-9  # 800 nm in meters

# Energy emitted from 0 to 800 nm
energy_below_800nm, _ = quad(lambda wl: planck_lambda(wl, T_Kelvin), 1e-9, lambda_limit)

# Total energy emitted (0 to infinity)
energy_total, _ = quad(lambda wl: planck_lambda(wl, T_Kelvin), 1e-9, np.inf)

# Percentage below 800 nm
percentage_below_800nm = (energy_below_800nm / energy_total) * 100

print(f"Percentage of energy below 800 nm: {percentage_below_800nm:.2f}%")
