import scipy.constants as cst


def radiative_heat_flux_between_plates(
    T1: float, T2: float, epsilon1: float, epsilon2: float
):
    return cst.Stefan_Boltzmann * (T1**4 - T2**4) / (1 / epsilon1 + 1 / epsilon2 - 1)
