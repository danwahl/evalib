import numpy as np
import pandas as pd
import pytest

from evalib import bootstrap


def mean_score(df: pd.DataFrame) -> dict[str, float]:
    return {"score": df["value"].mean()}


def test_constant_scores_have_zero_width():
    df = pd.DataFrame({"model": "m", "item": range(10), "value": 1.0})
    out = bootstrap(df, mean_score, by="model", cluster="item", n=50)
    assert out.loc["m", ("score", "lo")] == out.loc["m", ("score", "hi")] == 1.0


def test_interval_matches_normal_approximation():
    rng = np.random.default_rng(1)
    values = rng.integers(0, 2, size=400).astype(float)
    df = pd.DataFrame({"model": "m", "item": range(400), "value": values})
    out = bootstrap(df, mean_score, by="model", cluster="item", n=2000)
    p = values.mean()
    half = 1.96 * np.sqrt(p * (1 - p) / len(values))
    lo, hi = out.loc["m", ("score", "lo")], out.loc["m", ("score", "hi")]
    assert abs((hi - lo) / 2 - half) < 0.2 * half
    assert lo < p < hi


def test_resamples_clusters_within_strata():
    # Two questions with three epochs each; every replicate must keep three
    # rows per question, drawn as whole epochs.
    df = pd.DataFrame(
        {
            "model": "m",
            "question": ["a"] * 3 + ["b"] * 3,
            "epoch": [1, 2, 3] * 2,
            "value": [1.0, 2.0, 3.0, 10.0, 20.0, 30.0],
        }
    )
    seen = []

    def stat(g: pd.DataFrame) -> dict[str, float]:
        counts = g.groupby("question").size()
        seen.append((counts["a"], counts["b"]))
        return {"score": g["value"].mean()}

    bootstrap(df, stat, by="model", cluster="epoch", strata="question", n=20)
    assert set(seen) == {(3, 3)}


def test_groups_by_model():
    df = pd.DataFrame(
        {
            "model": ["a", "a", "b", "b"],
            "item": [1, 2, 1, 2],
            "value": [0.0, 0.0, 1.0, 1.0],
        }
    )
    out = bootstrap(df, mean_score, by="model", cluster="item", n=10)
    assert list(out.index) == ["a", "b"]
    assert out.loc["b", ("score", "value")] == 1.0


def test_group_intervals_do_not_depend_on_other_groups():
    rng = np.random.default_rng(2)
    df = pd.DataFrame(
        {"model": ["a"] * 30 + ["b"] * 30, "item": list(range(30)) * 2}
    ).assign(value=rng.normal(size=60))
    both = bootstrap(df, mean_score, by="model", cluster="item", n=100)
    alone = bootstrap(
        df[df.model == "b"], mean_score, by="model", cluster="item", n=100
    )
    assert both.loc["b"].equals(alone.loc["b"])


def test_rejects_empty_and_missing_keys():
    with pytest.raises(ValueError):
        bootstrap(
            pd.DataFrame(columns=["model", "item", "value"]),
            mean_score,
            "model",
            "item",
        )
    df = pd.DataFrame({"model": "m", "item": [1, None], "value": [0.0, 1.0]})
    with pytest.raises(ValueError):
        bootstrap(df, mean_score, by="model", cluster="item")


def test_multi_column_by():
    df = pd.DataFrame(
        {"model": "m", "task": ["x", "x", "y", "y"], "item": [1, 2, 1, 2], "value": 1.0}
    )
    out = bootstrap(df, mean_score, by=["model", "task"], cluster="item", n=5)
    assert list(out.index) == [("m", "x"), ("m", "y")]
