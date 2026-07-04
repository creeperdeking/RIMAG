#!/usr/bin/env python3

import argparse
import json
import math
from statistics import NormalDist


def t_critical_975(df: int) -> float:
    """
    Two-sided 95% t critical value: t_{0.975, df}.

    Uses scipy if available. Falls back to normal approximation if scipy
    is unavailable. The fallback is fine for large n_batches.
    """
    try:
        from scipy.stats import t
        return float(t.ppf(0.975, df))
    except ImportError:
        return NormalDist().inv_cdf(0.975)


def as_list(x):
    if isinstance(x, list):
        return x
    return [x]


def scalar_or_list(x):
    return x[0] if len(x) == 1 else x


def combine_quantity_percent_ci(mean1, ci95p_1, n1, mean2, ci95p_2, n2):
    """
    Combine two independent Monte Carlo estimates.

    mean1, mean2:
        Tally means.

    ci95p_1, ci95p_2:
        95% confidence interval half-widths in percent.

        Example:
            ci95p = 3.5 means +/- 3.5%

    n1, n2:
        Active batch counts.

    Returns:
        combined_mean, combined_ci95_percent
    """
    if n1 < 2 or n2 < 2:
        raise ValueError("Each run must have at least 2 active batches.")

    if mean1 == 0.0 or mean2 == 0.0:
        raise ValueError(
            "Cannot convert percent uncertainty to absolute uncertainty "
            "when a run mean is zero."
        )

    # Convert percent CI half-widths to absolute CI half-widths.
    ci95_abs_1 = abs(mean1) * ci95p_1 / 100.0
    ci95_abs_2 = abs(mean2) * ci95p_2 / 100.0

    # Convert 95% CI half-widths to standard errors.
    t1 = t_critical_975(n1 - 1)
    t2 = t_critical_975(n2 - 1)

    se1 = ci95_abs_1 / t1
    se2 = ci95_abs_2 / t2

    # Reconstruct per-batch sample variances.
    s1_sq = n1 * se1**2
    s2_sq = n2 * se2**2

    n_total = n1 + n2

    # Combined mean.
    mean_c = (n1 * mean1 + n2 * mean2) / n_total

    # Pooled variance, including the difference between the two run means.
    numerator = (
        (n1 - 1) * s1_sq
        + (n2 - 1) * s2_sq
        + n1 * (mean1 - mean_c) ** 2
        + n2 * (mean2 - mean_c) ** 2
    )

    s_c_sq = numerator / (n_total - 1)

    se_c = math.sqrt(s_c_sq / n_total)

    t_c = t_critical_975(n_total - 1)
    ci95_abs_c = t_c * se_c

    if mean_c == 0.0:
        raise ValueError(
            "Combined mean is zero, so percent uncertainty is undefined."
        )

    ci95p_c = 100.0 * ci95_abs_c / abs(mean_c)

    return mean_c, ci95p_c


def combine_json_pair(run1, run2):
    n1 = int(run1["n_batches"])
    n2 = int(run2["n_batches"])

    means1 = as_list(run1["ddd"])
    means2 = as_list(run2["ddd"])

    ci1 = as_list(run1["ddd_ci95p"])
    ci2 = as_list(run2["ddd_ci95p"])

    if not (len(means1) == len(means2) == len(ci1) == len(ci2)):
        raise ValueError("Length mismatch between ddd and ddd_ci95p fields.")

    combined_means = []
    combined_ci95p = []

    for m1, c1, m2, c2 in zip(means1, ci1, means2, ci2):
        mean_c, ci95p_c = combine_quantity_percent_ci(
            float(m1),
            float(c1),
            n1,
            float(m2),
            float(c2),
            n2,
        )

        combined_means.append(mean_c)
        combined_ci95p.append(ci95p_c)

    return {
        "ddd": combined_means,
        "ddd_ci95p": scalar_or_list(combined_ci95p),
        "n_batches": n1 + n2,
    }


def combine_json(*runs):
    if len(runs) < 2:
        raise ValueError("At least two runs are required to combine.")

    combined = runs[0]
    for run in runs[1:]:
        combined = combine_json_pair(combined, run)
    return combined


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Combine two or more independent OpenMC ddd JSON result files."
        )
    )

    parser.add_argument(
        "runs",
        nargs="+",
        metavar="INPUT",
        help="Two or more JSON files to combine",
    )
    parser.add_argument("output", help="Combined output JSON file")

    args = parser.parse_args()

    if len(args.runs) < 2:
        parser.error("At least two input JSON files are required.")

    runs = []
    for path in args.runs:
        with open(path, "r") as f:
            runs.append(json.load(f))

    combined = combine_json(*runs)

    with open(args.output, "w") as f:
        json.dump(combined, f, indent=2)

    print(f"Wrote combined result to {args.output}")


if __name__ == "__main__":
    main()