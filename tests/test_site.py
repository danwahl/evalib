import pytest

from evalib.cli import main
from evalib.site import build

from .test_results import board

README = "# My Eval\n\nIntro.\n\n[![GitHub](https://img.shields.io/badge/x-y)](https://github.com/x/y) [![Site](https://img.shields.io/badge/a-b)](https://x.github.io/y/)\n\n<!-- leaderboard:start -->\n\n| a |\n|---|\n| 1 |\n\n<!-- leaderboard:end -->\n\n## Method\n\n```\n# not a title\n```\n"


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text(README)
    b = board()
    b.notes = ["See [Usage](#usage) & more."]
    b.rows[0]["name"] = "<b>beta</b>"
    b.save(tmp_path / "results.json")
    (tmp_path / "CITATION.cff").write_text(
        "cff-version: 1.2.0\ntitle: My Eval & Co\nauthors:\n  - family-names: Wahl\n    given-names: Dan\ndate-released: 2026-10-01\nrepository-code: https://github.com/x/my_repo\n"
    )
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "c.png").write_bytes(b"png")
    return tmp_path


def test_build(repo):
    out = build(repo="x/y")
    html = (out / "index.html").read_text()
    assert "<title>My Eval</title>" in html
    assert 'id="leaderboard"' in html and "<td>1</td>" not in html
    assert 'href="#leaderboard"' in html
    assert "# not a title" in html
    assert "shields.io" not in html
    assert "@misc{wahl2026" in html and "author = {Wahl, Dan}" in html
    assert "title = {{My Eval \\&amp; Co}}" in html
    assert "url = {https://github.com/x/my_repo}" in html
    assert 'data-kind="baseline"' in html
    assert "&lt;b&gt;beta&lt;/b&gt;" in html and "<b>beta</b>" not in html
    assert '<a href="#usage">Usage</a> &amp; more.' in html
    assert (out / "results.json").exists()
    assert (out / "images" / "c.png").read_bytes() == b"png"


def test_build_without_marker_or_title(repo):
    (repo / "README.md").write_text("Intro only.\n")
    html = (build() / "index.html").read_text()
    assert "<title>Test</title>" in html
    assert 'id="leaderboard"' not in html and 'href="#leaderboard"' not in html


def test_build_rejects_assets_outside_repo(repo):
    with pytest.raises(ValueError):
        build(assets=["../secret"])


def test_cli(repo, monkeypatch):
    monkeypatch.setattr("sys.argv", ["evalib", "site", "--out", "public"])
    main()
    assert (repo / "public" / "index.html").exists()


def test_ticks_and_labels():
    from evalib.site import _tick_label, _ticks

    assert _ticks(57.9, 100) == [50, 60, 70, 80, 90, 100]
    assert _ticks(0.1, 0.3) == [0.1, 0.15, 0.2, 0.25, 0.3]
    assert _ticks(0.5, 0.5) == [0.45, 0.475, 0.5, 0.525, 0.55]
    assert _ticks(-3, 2) == [-3, -2, -1, 0, 1, 2]
    assert [_tick_label(v, "pct") for v in _ticks(0, 0.012)] == [
        "0%",
        "0.25%",
        "0.5%",
        "0.75%",
        "1%",
        "1.25%",
    ]
