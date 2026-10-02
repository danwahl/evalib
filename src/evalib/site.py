"""Build a static landing page from README.md, results.json and CITATION.cff."""

import math
import re
import shutil
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, PackageLoader, select_autoescape
from markdown_it import MarkdownIt
from markupsafe import Markup

from evalib.results import MARKER, Leaderboard, _has_interval, _key, fmt

# A line made only of badge images, optionally linked, which the site's header
# replaces. Only lines before the first section heading are checked.
BADGES = re.compile(
    r"^(?:\s*\[?!\[[^\]]*\]\([^)]*(?:shields\.io|badge)[^)]*\)(?:\]\([^)]*\))?)+\s*$\n?",
    re.M,
)
BLOCK = re.compile(rf"<!-- {MARKER}:start -->.*?<!-- {MARKER}:end -->", re.S)
DEFAULT_ASSETS = ["images"]

md = MarkdownIt("commonmark").enable(["table", "strikethrough"])


def build(
    out: str | Path = "_site",
    readme: str | Path = "README.md",
    results: str | Path = "results.json",
    citation: str | Path = "CITATION.cff",
    assets: list[str] = DEFAULT_ASSETS,
    repo: str | None = None,
    data_url: str | None = None,
) -> Path:
    """Write index.html and its assets to `out`.

    The README supplies the page content and is trusted: its HTML passes
    through unescaped. If it has a leaderboard block and results.json exists,
    the block becomes a sortable table with confidence intervals.
    CITATION.cff, if present, adds a BibTeX block. `assets` are files or
    directories the README references, given relative to the working
    directory and copied to the same place under `out`.
    """
    out = Path(out)
    for asset in assets:
        if Path(asset).is_absolute() or ".." in Path(asset).parts:
            raise ValueError(f"asset {asset} must be a relative path inside the repo")
    out.mkdir(parents=True, exist_ok=True)

    board = Leaderboard.load(results) if Path(results).exists() else None
    title, text = _split_title(Path(readme).read_text())
    head, sep, rest = text.partition("\n#")
    text = BADGES.sub("", head) + sep + rest
    title = title or (board.name if board else "")
    body = md.render(text)

    if board is not None and BLOCK.search(body):
        table = _env().get_template("table.html.j2").render(board=_table(board))
        body = BLOCK.sub(lambda _: table, body)
        shutil.copy(results, out / "results.json")
    else:
        board = None

    cite = _citation(Path(citation)) if Path(citation).exists() else None

    html = (
        _env()
        .get_template("index.html.j2")
        .render(
            title=title,
            body=body,
            board=board,
            cite=cite,
            repo=repo,
            data_url=data_url,
        )
    )
    (out / "index.html").write_text(html)

    for asset in assets:
        src = Path(asset)
        if src.is_dir():
            shutil.copytree(src, out / src, dirs_exist_ok=True)
        elif src.exists():
            (out / src).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, out / src)
    return out


def _env() -> Environment:
    return Environment(
        loader=PackageLoader("evalib", "templates"),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _split_title(text: str) -> tuple[str, str]:
    """Take a leading `# heading` out of the README to use as the page title."""
    m = re.match(r"\s*# (.+)\n?", text)
    if not m:
        return "", text
    return m.group(1).strip(), text[m.end() :]


def _table(board: Leaderboard) -> dict[str, Any]:
    """Shape a leaderboard for the table template, with bar positions."""
    head = board.columns[0]
    cells = [r["scores"].get(head.key, {}) for r in board.rows]
    bounds = [
        v
        for c in cells
        for v in (c.get("lo"), c.get("value"), c.get("hi"))
        if v is not None
    ]
    ticks = _ticks(min(bounds), max(bounds)) if bounds else [0.0, 1.0]
    lo, span = ticks[0], ticks[-1] - ticks[0]

    def pos(v: float | None) -> float | None:
        return None if v is None else round(100 * (v - lo) / span, 2)

    rows = []
    for order, (row, rank) in enumerate(board.ranks()):
        cols = []
        for col in board.columns:
            cell = row["scores"].get(col.key)
            if cell is None:
                cols.append({"text": "", "sort": ""})
                continue
            entry: dict[str, Any] = {
                "text": fmt(cell["value"], col.format),
                "sort": _key(cell["value"]),
            }
            if _has_interval(cell):
                entry["interval"] = (
                    f"{fmt(cell['lo'], col.format)}–{fmt(cell['hi'], col.format)}"
                )
            if col is head:
                entry["bar"] = {"value": pos(cell["value"])}
                if _has_interval(cell):
                    entry["bar"] |= {"lo": pos(cell["lo"]), "hi": pos(cell["hi"])}
            cols.append(entry)
        rows.append(
            {
                "rank": "" if rank is None else rank,
                "order": order,
                "name": row["name"] + row.get("flag", ""),
                "info": [row.get("info", {}).get(k, "") for k in board.info],
                "kind": row["kind"],
                "cols": cols,
            }
        )
    return {
        "columns": board.columns,
        "info": list(board.info.values()),
        "rows": rows,
        "notes": [Markup(md.renderInline(note)) for note in board.notes],
        "updated": board.updated,
        "kinds": sorted({r["kind"] for r in board.rows} - {"model"}),
        "intervals": any("interval" in c for r in rows for c in r["cols"]),
        "ticks": [{"pos": pos(v), "label": _tick_label(v, head.format)} for v in ticks],
    }


def _ticks(lo: float, hi: float, target: int = 5) -> list[float]:
    """Round axis ticks that cover [lo, hi], about `target` intervals apart."""
    if hi <= lo:
        pad = abs(lo) * 0.1 or 1.0
        lo, hi = lo - pad, hi + pad
    raw = (hi - lo) / target
    magnitude = 10 ** math.floor(math.log10(raw))
    step = next(m * magnitude for m in (1, 2, 2.5, 5, 10) if m * magnitude >= raw)
    start, stop = math.floor(lo / step), math.ceil(hi / step)
    # Twelve significant digits clear float noise such as 0.30000000000000004.
    return [float(f"{i * step:.12g}") for i in range(start, stop + 1)]


def _tick_label(value: float, spec: str) -> str:
    if spec == "pct":
        return f"{value * 100:.12g}%"
    return f"{value:.12g}"


def _citation(path: Path) -> dict[str, str]:
    """Render CITATION.cff as BibTeX, preferring its preferred-citation."""
    cff = yaml.safe_load(path.read_text())
    ref = cff.get("preferred-citation", cff)
    authors = " and ".join(
        f"{a.get('family-names', '')}, {a.get('given-names', '')}".strip(", ")
        if "family-names" in a
        else a.get("name", "")
        for a in ref.get("authors", [])
    )
    year = str(ref.get("year") or str(ref.get("date-released", ""))[:4])
    kind = {"article": "article", "report": "techreport"}.get(
        ref.get("type", ""), "misc"
    )
    key = (
        re.sub(
            r"\W", "", (ref.get("authors") or [{}])[0].get("family-names", "cite")
        ).lower()
        + year
    )
    fields = {
        "title": ref.get("title"),
        "author": authors,
        "year": year,
        "journal": ref.get("journal"),
        "doi": ref.get("doi"),
        "url": ref.get("url") or ref.get("repository-code"),
        "note": f"Version {ref['version']}" if ref.get("version") else None,
    }
    # url and doi are read verbatim, so only the text fields are escaped.
    fields = {
        k: v if k in ("url", "doi") else _bibtex_escape(v)
        for k, v in fields.items()
        if v
    }
    if "title" in fields:
        # Double braces keep BibTeX from lowercasing names like SpeciEval.
        fields["title"] = "{" + fields["title"] + "}"
    body = ",\n".join(f"  {k} = {{{v}}}" for k, v in fields.items())
    return {"bibtex": f"@{kind}{{{key},\n{body}\n}}"}


def _bibtex_escape(value: str) -> str:
    return re.sub(r"([&%$#_{}])", r"\\\1", value)
