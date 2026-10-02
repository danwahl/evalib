import pandas as pd
import pytest

from evalib import Column, Leaderboard, update_readme


def board() -> Leaderboard:
    b = Leaderboard(
        "Test",
        [
            Column("total", "Total", "lower", "pct"),
            Column("part", "Part", "lower", "pct"),
        ],
    )
    scores = pd.DataFrame(
        {
            ("total", "value"): [0.3, 0.2],
            ("total", "lo"): [0.25, 0.15],
            ("total", "hi"): [0.35, 0.25],
            ("part", "value"): [0.1, 0.5],
            ("part", "lo"): [0.05, 0.4],
            ("part", "hi"): [0.15, 0.6],
        },
        index=["beta", "alpha"],
    )
    b.add(scores, flags={"beta": "*"})
    b.add(pd.DataFrame({"total": [0.25]}, index=["Humans"]), kind="baseline")
    return b


def test_ranked_puts_best_first_and_skips_baselines_in_rank():
    rows = board().ranked()
    assert [r["name"] for r in rows] == ["alpha", "Humans", "beta"]
    table = board().markdown()
    assert "| 1 | alpha | **20% (15%–25%)** | 50% |" in table
    assert "|  | _Humans_ | 25% |  |" in table
    assert "| 2 | beta* | 30% (25%–35%) | **10%** |" in table


def test_round_trip(tmp_path):
    path = tmp_path / "results.json"
    board().save(path)
    loaded = Leaderboard.load(path)
    assert loaded.markdown() == board().markdown()


def test_update_readme(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text(
        "# X\n\n<!-- leaderboard:start -->\nold\n<!-- leaderboard:end -->\n\nMore\n"
    )
    update_readme("new table", readme)
    assert (
        readme.read_text()
        == "# X\n\n<!-- leaderboard:start -->\n\nnew table\n\n<!-- leaderboard:end -->\n\nMore\n"
    )
    readme.write_text("no markers")
    with pytest.raises(ValueError):
        update_readme("t", readme)


def test_ties_share_a_rank_and_tuple_names_are_joined():
    b = Leaderboard("T", [Column("s", "S")])
    b.add(
        pd.DataFrame({"s": [1.0, 1.0, 0.5]}, index=[("m", "x"), ("m", "y"), ("n", "x")])
    )
    assert [(r["name"], rank) for r, rank in b.ranks()] == [
        ("m / x", 1),
        ("m / y", 1),
        ("n / x", 3),
    ]


def test_markdown_without_upper_bound_and_with_notes():
    b = Leaderboard("T", [Column("s", "S")], notes=["\\* one", "† two"])
    b.add(
        pd.DataFrame(
            {("s", "value"): [0.5], ("s", "lo"): [0.4], ("s", "hi"): [None]},
            index=["m"],
        )
    )
    table = b.markdown()
    assert "| 1 | m | **0.50** |" in table
    assert table.endswith("\\* one\n\n† two")


def test_tied_best_is_not_bolded():
    b = Leaderboard("T", [Column("s", "S"), Column("t", "T")])
    b.add(pd.DataFrame({"s": [2.0, 1.0], "t": [7.0, 7.0]}, index=["a", "b"]))
    assert "| 1 | a | **2.00** | 7.00 |" in b.markdown()


def test_info_columns():
    b = Leaderboard("T", [Column("s", "S")], info={"provider": "Provider"})
    b.add(
        pd.DataFrame({"s": [1.0]}, index=["gpt"]),
        info=pd.DataFrame({"provider": ["OpenAI"]}, index=["gpt"]),
    )
    b.add(pd.DataFrame({"s": [0.5]}, index=["Humans"]), kind="baseline")
    table = b.markdown()
    assert "| # | name | Provider | S |" in table and "|--:|:--|:--|--:|" in table
    assert "| 1 | gpt | OpenAI | **1.00** |" in table
    assert "|  | _Humans_ |  | 0.50 |" in table


def test_provider():
    from evalib import provider

    assert provider("openrouter/x-ai/grok-4") == "x-ai"
    assert provider("anthropic/claude-x") == "anthropic"
    assert provider("model") == ""


def test_float_noise_ties():
    board = Leaderboard("Test", [Column("score", "Score", "lower")])
    board.add(
        pd.DataFrame({"score": [(0.1 + 0.2) / 3, 0.3 / 3, 0.2]}, index=["b", "a", "c"])
    )
    assert [(r["name"], rank) for r, rank in board.ranks()] == [
        ("a", 1),
        ("b", 1),
        ("c", 3),
    ]
    assert "**" not in board.markdown()
