# evalib

Shared leaderboard, statistics and landing-page tooling for [Inspect](https://inspect.aisi.org.uk/) evals.

Each eval keeps its own analysis script, which decides which runs count and how they are scored. evalib supplies the parts that are the same everywhere:

- `bootstrap`: percentile confidence intervals that resample whole clusters (epochs, items) within strata (questions, tasks)
- `Leaderboard`: a `results.json` file of scores, intervals and reference rows such as human baselines
- `update_readme`: writes the leaderboard table into the README between `<!-- leaderboard:start -->` and `<!-- leaderboard:end -->`
- `evalib site`: builds a static landing page from the README, `results.json` and `CITATION.cff`

## Usage

```python
from evalib import Column, Leaderboard, bootstrap, update_readme

# One row per scored unit, e.g. a sample epoch.
scores = bootstrap(samples, statistic, by="model", cluster="epoch", strata="question")

board = Leaderboard("MyEval", [Column("score", "Score", "higher")])
board.add(scores)
board.add(human_baselines, kind="human")
board.save("results.json")
update_readme(board.markdown())
```

`statistic` takes one model's rows and returns a dict of named scores, so composite scores get intervals the same way simple means do.

To build the site, for example in a GitHub Pages workflow:

```bash
uvx --from git+https://github.com/danwahl/evalib evalib site --repo owner/repo
```

The page goes to `_site/`. The `images/` directory is copied by default; pass `--assets` to change that.

## Development

```bash
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run mypy src
```
