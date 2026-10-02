"""Bootstrap confidence intervals for leaderboard scores."""

import warnings
from collections.abc import Callable, Sequence

import numpy as np
import pandas as pd

Statistic = Callable[[pd.DataFrame], dict[str, float]]

CI = 0.95


def bootstrap(
    samples: pd.DataFrame,
    statistic: Statistic,
    by: str | Sequence[str],
    cluster: str | Sequence[str],
    strata: str | Sequence[str] | None = None,
    n: int = 1000,
    seed: int = 0,
) -> pd.DataFrame:
    """Score each group of `samples` with a 95% percentile bootstrap interval.

    `samples` holds one row per scored unit, such as a sample epoch. Rows are
    split into leaderboard rows by `by`, and `statistic` turns one row's
    samples into named scores. Each replicate redraws whole clusters (rows
    sharing the `cluster` columns) with replacement, separately within each
    stratum, so it keeps the design of the original run. For example, an eval
    with a fixed questionnaire run for several epochs resamples epochs within
    each question, while one with many items resamples items within each task.

    Every group draws from a generator seeded with `seed`, so a group's
    interval does not change when other groups are added.

    Returns a frame indexed by `by`, with a (score, "value" | "lo" | "hi")
    column for each score. The value is the statistic on the full data.
    """
    by_cols, cluster_cols = _cols(by), _cols(cluster)
    strata_cols = _cols(strata) if strata is not None else []
    if samples.empty:
        raise ValueError("no samples to bootstrap")
    keys = by_cols + cluster_cols + strata_cols
    if samples[keys].isna().any().any():
        raise ValueError(f"missing values in {keys}")
    alpha = (1 - CI) / 2

    rows = {}
    for key, group in samples.groupby(by_cols, sort=True):
        group = group.reset_index(drop=True)
        draws = _cluster_draws(group, cluster_cols, strata_cols)
        rng = np.random.default_rng(seed)
        boot = pd.DataFrame(
            [statistic(group.iloc[_resample(draws, rng)]) for _ in range(n)]
        )
        row: dict[tuple[str, str], float] = {}
        for score, value in statistic(group).items():
            col = boot[score]
            missing = int(col.isna().sum())
            if missing and not np.isnan(value):
                warnings.warn(
                    f"{key}: {score} is undefined in {missing} of {n} replicates",
                    stacklevel=2,
                )
            col = col.dropna()
            row[(score, "value")] = value
            row[(score, "lo")] = float(col.quantile(alpha)) if len(col) else np.nan
            row[(score, "hi")] = float(col.quantile(1 - alpha)) if len(col) else np.nan
        rows[key[0] if len(by_cols) == 1 else key] = row

    out = pd.DataFrame.from_dict(rows, orient="index")
    out.index.names = by_cols
    return out


def _cols(cols: str | Sequence[str]) -> list[str]:
    return [cols] if isinstance(cols, str) else list(cols)


def _cluster_draws(
    group: pd.DataFrame, cluster_cols: list[str], strata_cols: list[str]
) -> list[list[np.ndarray]]:
    """Row positions of each cluster, grouped by stratum."""
    positions = group.groupby(strata_cols + cluster_cols, sort=True).indices
    by_stratum: dict[tuple, list[np.ndarray]] = {}
    for key, idx in positions.items():
        key = key if isinstance(key, tuple) else (key,)
        by_stratum.setdefault(key[: len(strata_cols)], []).append(np.asarray(idx))
    return list(by_stratum.values())


def _resample(draws: list[list[np.ndarray]], rng: np.random.Generator) -> np.ndarray:
    """Row positions for one replicate: clusters redrawn within each stratum."""
    return np.concatenate(
        [
            members[i]
            for members in draws
            for i in rng.integers(len(members), size=len(members))
        ]
    )
