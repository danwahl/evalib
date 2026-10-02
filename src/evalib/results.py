"""The results.json leaderboard file and its README table."""

import json
import math
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Literal

import pandas as pd

MARKER = "leaderboard"


@dataclass
class Column:
    """A leaderboard score column.

    `format` is "pct" for fractions shown as percentages, or a Python format
    spec such as ".2f".
    """

    key: str
    label: str
    better: Literal["higher", "lower"] = "higher"
    format: str = ".2f"
    description: str = ""


@dataclass
class Leaderboard:
    """Scores per model, plus optional reference rows such as human baselines.

    The first column is the headline score that ranks the table. `info` maps
    the keys of descriptive text columns, such as a provider, to their labels.
    """

    name: str
    columns: list[Column]
    info: dict[str, str] = field(default_factory=dict)
    rows: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    updated: str = field(default_factory=lambda: date.today().isoformat())

    def add(
        self,
        scores: pd.DataFrame,
        kind: str = "model",
        flags: dict[str, str] | None = None,
        info: pd.DataFrame | None = None,
    ) -> None:
        """Add rows from a frame indexed by name.

        `scores` is either the output of evalib.bootstrap, with
        (score, value/lo/hi) columns, or plain values with one column per score.
        `flags` maps a row name to a short marker, such as "*", explained in
        the notes. `info` holds the text columns, indexed like `scores`.
        """
        flags = flags or {}
        if info is not None:
            info = info[~info.index.duplicated()]
        for index, row in scores.iterrows():
            name = (
                " / ".join(map(str, index)) if isinstance(index, tuple) else str(index)
            )
            entry: dict[str, Any] = {"name": name, "kind": kind, "scores": {}}
            if name in flags:
                entry["flag"] = flags[name]
            if info is not None and index in info.index:
                entry["info"] = {
                    k: str(info.at[index, k])
                    for k in self.info
                    if k in info and pd.notna(info.at[index, k])
                }
            for col in self.columns:
                if isinstance(scores.columns, pd.MultiIndex):
                    cell = {
                        k: _num(row.get((col.key, k))) for k in ("value", "lo", "hi")
                    }
                else:
                    cell = {"value": _num(row.get(col.key))}
                if cell["value"] is not None:
                    entry["scores"][col.key] = cell
            self.rows.append(entry)

    def ranked(self) -> list[dict[str, Any]]:
        """Rows by headline score, best first, ties broken by name."""
        head = self.columns[0]
        sign = -1 if head.better == "higher" else 1

        def key(row: dict[str, Any]) -> tuple:
            v = row["scores"].get(head.key, {}).get("value")
            return (v is None, sign * _key(v) if v is not None else 0, row["name"])

        return sorted(self.rows, key=key)

    def ranks(self) -> list[tuple[dict[str, Any], int | None]]:
        """Ranked rows with their competition rank (1, 2, 2, 4), None for references."""
        head = self.columns[0].key
        out: list[tuple[dict[str, Any], int | None]] = []
        count, rank, last = 0, 0, None
        for row in self.ranked():
            if row["kind"] != "model":
                out.append((row, None))
                continue
            count += 1
            value = row["scores"].get(head, {}).get("value")
            value = None if value is None else _key(value)
            if value != last:
                rank, last = count, value
            out.append((row, rank))
        return out

    def save(self, path: str | Path = "results.json") -> None:
        data = asdict(self)
        data["rows"] = self.ranked()
        Path(path).write_text(json.dumps(data, indent=1) + "\n")

    @classmethod
    def load(cls, path: str | Path = "results.json") -> "Leaderboard":
        data = json.loads(Path(path).read_text())
        data["columns"] = [Column(**c) for c in data["columns"]]
        return cls(**data)

    def markdown(self, interval: bool = True) -> str:
        """A markdown table, with the headline interval when available."""
        head = self.columns[0]
        best = {c.key: _best(self.rows, c) for c in self.columns}
        lines = [
            "| # | "
            + " | ".join(
                ["Name", *self.info.values()] + [c.label for c in self.columns]
            )
            + " |",
            "|--:|:--|" + ":--|" * len(self.info) + "--:|" * len(self.columns),
        ]
        for row, rank in self.ranks():
            cells = ["" if rank is None else str(rank), _name(row)]
            cells += [row.get("info", {}).get(k, "") for k in self.info]
            for col in self.columns:
                cell = row["scores"].get(col.key)
                if cell is None:
                    cells.append("")
                    continue
                text = fmt(cell["value"], col.format)
                if interval and col is head and _has_interval(cell):
                    text += f" ({fmt(cell['lo'], col.format)}–{fmt(cell['hi'], col.format)})"
                if row["kind"] == "model" and _key(cell["value"]) == best[col.key]:
                    text = f"**{text}**"
                cells.append(text)
            lines.append("| " + " | ".join(cells) + " |")
        out = "\n".join(lines)
        if self.notes:
            out += "\n\n" + "\n\n".join(self.notes)
        return out


def fmt(value: float, spec: str) -> str:
    if spec == "pct":
        return f"{value * 100:.0f}%"
    return format(value, spec)


def update_readme(
    table: str, path: str | Path = "README.md", marker: str = MARKER
) -> None:
    """Replace the text between <!-- marker:start --> and <!-- marker:end -->."""
    path = Path(path)
    text = path.read_text()
    start, end = f"<!-- {marker}:start -->", f"<!-- {marker}:end -->"
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if not pattern.search(text):
        raise ValueError(f"{path} has no {start} ... {end} block")
    path.write_text(pattern.sub(lambda _: f"{start}\n\n{table}\n\n{end}", text))


def _num(v: Any) -> float | None:
    if v is None:
        return None
    v = float(v)
    return None if math.isnan(v) else v


def _has_interval(cell: dict[str, Any]) -> bool:
    return cell.get("lo") is not None and cell.get("hi") is not None


def _key(value: float) -> float:
    """A score rounded past float noise, for ranking and finding ties."""
    return round(value, 9)


def _best(rows: list[dict[str, Any]], col: Column) -> float | None:
    """The column's best model value, if exactly one model has it."""
    values = [
        _key(r["scores"][col.key]["value"])
        for r in rows
        if r["kind"] == "model" and col.key in r["scores"]
    ]
    if not values:
        return None
    best = max(values) if col.better == "higher" else min(values)
    # A shared best value highlights nothing, so only a unique one is bolded.
    return best if values.count(best) == 1 else None


def _name(row: dict[str, Any]) -> str:
    name = row["name"] + row.get("flag", "")
    return f"_{name}_" if row["kind"] != "model" else name
