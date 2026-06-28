#!/usr/bin/env python3

import argparse
import json
import math
from statistics import NormalDist


def t_critical_975(df: int) -> float:
    """
    Two-sided 95% t critical value: t_{0.975, df}.

    Uses scipy if available. Falls back to normal approximation if scipy
    is unavailable, which is fine for large n_batches but less exact for
    small batch counts.
    """
    try:
        from scipy.stats import t
        return float(t.ppf(0.975, df))
    except ImportError:
        return NormalDist().inv_cdf(0.975)


def as_list(x):
    """Allow either scalar or length-N list values."""
    if isinstance(x, list):
        return x
    return [x]


def scalar_or_list(x):
    """Write single-value lists back as scalars only for CI fields if desired."""
    return x[0] if len(x) == 1 else x


def combine_quantity(mean1, ci1, n1, mean2, ci2, n2):
    """
    Combine two independent Monte Carlo estimates.

    mean1, mean2: sample means
    ci1, ci2: 95% confidence interval half-widths
    n1, n2: active batch counts

    Returns:
        combined_mean, combined_ci95
    """
    if n1 < 2 or n2 < 2:
        raise ValueError("Each run must have at least 2 batches.")

    t1 = t_critical_975(n1 - 1)
    t2 = t_critical_975(n2 - 1)

    # Convert 95% CI half-widths to standard errors.
    se1 = ci1 / t1
    se2 = ci2 / t2

    # Reconstruct per-batch sample variances.
    s1_sq = n1 * se1**2
    s2_sq = n2 * se2**2

    n_total = n1 + n2

    # Combined mean.
    mean_c = (n1 * mean1 + n2 * mean2) / n_total

    # Pooled variance including between-run mean difference.
    numerator = (
        (n1 - 1) * s1_sq
        + (n2 - 1) * s2_sq
        + n1 * (mean1 - mean_c) ** 2
        + n2 * (mean2 - mean_c) ** 2
    )

    s_c_sq = numerator / (n_total - 1)

    se_c = math.sqrt(s_c_sq / n_total)

    t_c = t_critical_975(n_total - 1)
    ci_c = t_c * se_c

    return mean_c, ci_c


def combine_json(run1, run2):
    n1 = int(run1["n_batches"])
    n2 = int(run2["n_batches"])

    output = {
        "n_batches": n1 + n2
    }

    for key in run1:
        if key == "n_batches" or key.endswith("_ci95p"):
            continue

        ci_key = f"{key}_ci95p"

        if ci_key not in run1:
            continue

        if key not in run2 or ci_key not in run2:
            raise KeyError(f"Missing '{key}' or '{ci_key}' in second JSON file.")

        means1 = as_list(run1[key])
        means2 = as_list(run2[key])
        cis1 = as_list(run1[ci_key])
        cis2 = as_list(run2[ci_key])

        if not (len(means1) == len(means2) == len(cis1) == len(cis2)):
            raise ValueError(f"Length mismatch for '{key}' and '{ci_key}'.")

        combined_means = []
        combined_cis = []

        for m1, c1, m2, c2 in zip(means1, cis1, means2, cis2):
            mean_c, ci_c = combine_quantity(
                float(m1),
                float(c1),
                n1,
                float(m2),
                float(c2),
                n2,
            )
            combined_means.append(mean_c)
            combined_cis.append(ci_c)

        # Preserve list structure for tally means.
        output[key] = combined_means
        output[ci_key] = scalar_or_list(combined_cis)

    return output


def main():
    parser = argparse.ArgumentParser(
        description="Combine two independent OpenMC tally result JSON files."
    )
    parser.add_argument("run1", help="First JSON file")
    parser.add_argument("run2", help="Second JSON file")
    parser.add_argument("output", help="Combined output JSON file")

    args = parser.parse_args()

    with open(args.run1, "r") as f:
        run1 = json.load(f)

    with open(args.run2, "r") as f:
        run2 = json.load(f)

    combined = combine_json(run1, run2)

    with open(args.output, "w") as f:
        json.dump(combined, f, indent=2)

    print(f"Wrote combined result to {args.output}")


if __name__ == "__main__":
    main()