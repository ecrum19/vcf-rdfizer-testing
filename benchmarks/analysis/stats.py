#!/usr/bin/env python3
"""Shared statistics for the benchmark analysis. numpy only — no scipy.

Two things are needed and nothing else:

* ``paired_ratio_ci`` — a bootstrap CI on the paired ratio between two
  configurations, for the equivalence claims in plan §1 and §2.3. Paired
  because the input and every other setting are identical within a pair; a
  ratio rather than a difference because the quantity that travels across
  input sizes is "x% slower", not "n seconds slower".

* ``loglog_slope`` — an OLS slope on log-log axes with a CI, for the scaling
  exponents in §2.2 and §3.1. The CI uses the t distribution, whose critical
  values are tabulated here so scipy is not a dependency.
"""

from __future__ import annotations

import math

import numpy as np

# Two-sided 95% t critical values by degrees of freedom. Small-sample
# benchmarks live at the top of this table, which is why it is worth having
# rather than approximating everything with 1.96.
_T95 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
    8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145,
    15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086,
    25: 2.060, 30: 2.042, 40: 2.021, 60: 2.000, 120: 1.980,
}


def t_critical_95(df: int) -> float:
    """Two-sided 95% t critical value, conservative between tabulated rows."""
    if df <= 0:
        return float("nan")
    if df in _T95:
        return _T95[df]
    smaller = [k for k in _T95 if k < df]
    if not smaller:
        return _T95[1]
    return _T95[max(smaller)]


def median(values) -> float:
    return float(np.median(np.asarray(values, dtype=float)))


def paired_ratio_ci(
    treatment,
    baseline,
    *,
    iterations: int = 20000,
    seed: int = 20260910,
    confidence: float = 0.90,
) -> dict:
    """Bootstrap CI on median(treatment) / median(baseline) over paired runs.

    ``treatment`` and ``baseline`` are equal-length sequences whose i-th entries
    are the two arms of the same repetition, in the order they ran. Resampling
    is by PAIR, which is what preserves the pairing that makes the comparison
    tight.

    Returns the point estimate as a relative difference (0.03 means treatment is
    3% slower) plus the CI bounds, so it can be compared directly against a
    stated equivalence margin.
    """
    t = np.asarray(treatment, dtype=float)
    b = np.asarray(baseline, dtype=float)
    if t.size != b.size:
        raise ValueError(f"unpaired input: {t.size} treatment vs {b.size} baseline")
    if t.size == 0:
        raise ValueError("no pairs")
    if np.any(b <= 0):
        raise ValueError("baseline contains a non-positive value; cannot form a ratio")

    point = float(np.median(t) / np.median(b))

    rng = np.random.default_rng(seed)
    n = t.size
    if n == 1:
        # One pair carries no sampling information. Say so rather than emitting
        # a zero-width interval that looks like certainty.
        return {
            "n_pairs": 1,
            "ratio": point,
            "relative_difference": point - 1.0,
            "ci_low": float("nan"),
            "ci_high": float("nan"),
            "confidence": confidence,
            "note": "a single pair has no CI; report the point estimate only",
        }

    idx = rng.integers(0, n, size=(iterations, n))
    ratios = np.median(t[idx], axis=1) / np.median(b[idx], axis=1)
    alpha = (1.0 - confidence) / 2.0
    low, high = np.quantile(ratios, [alpha, 1.0 - alpha])

    return {
        "n_pairs": int(n),
        "ratio": point,
        "relative_difference": point - 1.0,
        "ci_low": float(low) - 1.0,
        "ci_high": float(high) - 1.0,
        "confidence": confidence,
        "iterations": iterations,
        "seed": seed,
    }


def equivalence_verdict(result: dict, margin: float) -> dict:
    """Decide a stated equivalence margin against a paired CI.

    The margin is symmetric and expressed as a fraction (0.10 = +/-10%).
    Equivalence is declared only when the whole CI sits inside the corridor —
    a point estimate inside it is not enough, and a CI that merely overlaps
    zero is not evidence of equivalence.
    """
    low, high = result.get("ci_low"), result.get("ci_high")
    if low is None or high is None or math.isnan(low) or math.isnan(high):
        verdict = "INDETERMINATE"
        reason = "no CI available (too few pairs)"
    elif low >= -margin and high <= margin:
        verdict = "EQUIVALENT"
        reason = f"the whole {int(result['confidence'] * 100)}% CI lies inside +/-{margin:.0%}"
    elif low > margin or high < -margin:
        verdict = "DIFFERENT"
        reason = "the CI lies entirely outside the margin"
    else:
        verdict = "INCONCLUSIVE"
        reason = "the CI straddles the margin boundary; more repetitions needed"
    return {**result, "margin": margin, "verdict": verdict, "verdict_reason": reason}


def loglog_slope(x, y) -> dict:
    """OLS slope of log(y) on log(x), with a 95% CI and R^2.

    A slope near 1 means approximately linear empirical scaling over the
    measured range. It is not an algorithmic bound and must not be generalized
    beyond the points actually run.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    keep = (x > 0) & (y > 0) & np.isfinite(x) & np.isfinite(y)
    x, y = x[keep], y[keep]
    n = x.size
    if n < 2:
        return {"n": int(n), "slope": float("nan"),
                "note": "need at least 2 positive points to fit a slope"}

    lx, ly = np.log(x), np.log(y)
    slope, intercept = np.polyfit(lx, ly, 1)
    predicted = slope * lx + intercept
    residuals = ly - predicted
    ss_res = float(np.sum(residuals ** 2))
    ss_tot = float(np.sum((ly - ly.mean()) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")

    out = {
        "n": int(n),
        "slope": float(slope),
        "intercept": float(intercept),
        "r_squared": r_squared,
        "x_range": [float(x.min()), float(x.max())],
    }
    if n > 2:
        df = n - 2
        s_err = math.sqrt(ss_res / df)
        sxx = float(np.sum((lx - lx.mean()) ** 2))
        se_slope = s_err / math.sqrt(sxx) if sxx > 0 else float("nan")
        crit = t_critical_95(df)
        out.update({
            "slope_stderr": se_slope,
            "slope_ci_low": float(slope - crit * se_slope),
            "slope_ci_high": float(slope + crit * se_slope),
            "df": df,
        })
    else:
        out["note"] = "2 points fit a line exactly; no CI is available"
    return out
