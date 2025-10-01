import numpy as np
from math import sqrt
from scipy.integrate import solve_ivp
from scipy.optimize import root_scalar
import matplotlib.pyplot as plt


def _ode(s, y, mu, omega, g):
    r, z, X, Y = y
    T = sqrt(X * X + Y * Y)
    if T == 0.0:
        sr = 0.0
        sz = 0.0
    else:
        sr = X / T
        sz = Y / T
    dX = -mu * (omega**2) * r
    dY = -mu * g
    return [sr, sz, dX, dY]


def _integrate_with_X0(L, mu, omega, g, X0, r_top):
    Y0 = mu * g * L
    y0 = [r_top, 0.0, X0, Y0]
    return solve_ivp(
        lambda s, y: _ode(s, y, mu, omega, g),
        (0.0, L),
        y0,
        dense_output=True,
        rtol=1e-8,
        atol=1e-10,
        max_step=L / 500,
    )


def _residual(L, mu, omega, g, X0, r_top):
    sol = _integrate_with_X0(L, mu, omega, g, X0, r_top)
    return sol.y[2, -1]  # X(L)


def compute_shape(L, mu, omega, g=9.80665, r_top=1e-3):
    # Find a bracket for X0 (avoid trivial X0=0 root by using r_top>0)
    scale = mu * g * L * max(1.0, (omega**2) * L / g)
    bracket_pair = None
    for M in [1, 3, 10, 30, 100, 300, 1000]:
        a = -M * scale
        b = M * scale
        try:
            fa = _residual(L, mu, omega, g, a, r_top)
            fb = _residual(L, mu, omega, g, b, r_top)
            if np.isfinite(fa) and np.isfinite(fb) and fa * fb < 0:
                bracket_pair = (a, b)
                break
        except Exception:
            pass
    if bracket_pair is None:
        raise RuntimeError("Failed to bracket a solution for X0.")

    sol_root = root_scalar(
        lambda X0: _residual(L, mu, omega, g, X0, r_top),
        bracket=bracket_pair,
        method="brentq",
        xtol=1e-10,
        rtol=1e-10,
        maxiter=100,
    )
    if not sol_root.converged:
        raise RuntimeError("Root solve for X0 did not converge.")
    X0_star = sol_root.root

    sol = _integrate_with_X0(L, mu, omega, g, X0_star, r_top)
    s = np.linspace(0.0, L, 1000)
    y = sol.sol(s)
    r, z, X, Y = y
    theta = np.arctan2(X, Y)
    T = np.sqrt(X * X + Y * Y)
    z = z - z[-1]

    return {
        "s": s,
        "r": r,
        "z": z,
        "theta": theta,
        "T": T,
        "X0": X0_star,
        "Y0": mu * g * L,
        "r_top": r[0],
    }


def plot_string(results, L, mu, omega, g=9.80665):
    s = results["s"]
    r = results["r"]
    z = results["z"]
    theta = results["theta"]
    T = results["T"]

    plt.figure(figsize=(6, 8))
    plt.plot(r, z, linewidth=2)
    plt.gca().set_aspect("equal", adjustable="box")
    plt.xlabel("Radius r [m]")
    plt.ylabel("Height z [m] (tip at 0)")
    plt.title("Whirling massive string (uniform density)")
    plt.plot([r[0]], [z[0]], marker="o")
    plt.plot([r[-1]], [z[-1]], marker="s")
    plt.grid(True, which="both", linestyle="--", alpha=0.4)
    plt.show()

    theta_top_deg = np.degrees(theta[0])
    avg_theta_deg = np.degrees(np.median(theta))
    print(f"Median angle to vertical: {avg_theta_deg:.3f} deg")
    T_top = T[0]
    print(f"Top angle to vertical: {theta_top_deg:.3f} deg")
    print(f"Top tension: {T_top:.6g} N  (∝ mu)")
    print(f"Free-tip radius r_tip: {r[-1]:.6g} m")
    print([r[0]], [z[0]])
    for i in range(len(r)):
        if round(r[i], 1) == 0.6 + 1:
            print(i, r[i], z[i])


factor = 1.01
if __name__ == "__main__":
    # Example parameters (SI)
    L = 1.0 * factor  # [m]
    mu = 0.05 * 0.1 / factor  # [kg/m] -- only scales tension
    omega = np.pi * 2 * 1.5  # [rad/s]
    g = 9.80665  # [m/s^2]
    r_top = (
        0.6  # [m] attachment radius; set to 0 for on-axis (trivial straight solution)
    )

    res = compute_shape(L, mu, omega, g, r_top)
    plot_string(res, L, mu, omega, g)
