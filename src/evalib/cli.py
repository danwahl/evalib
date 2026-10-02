"""Command line entry point: `evalib readme` and `evalib site`."""

import argparse

from evalib.results import Leaderboard, update_readme
from evalib.site import DEFAULT_ASSETS, build


def main() -> None:
    parser = argparse.ArgumentParser(prog="evalib")
    sub = parser.add_subparsers(dest="command", required=True)

    readme = sub.add_parser(
        "readme", help="write results.json into the README leaderboard block"
    )
    readme.add_argument("--results", default="results.json")
    readme.add_argument("--readme", default="README.md")

    site = sub.add_parser("site", help="build the landing page")
    site.add_argument("--out", default="_site")
    site.add_argument("--readme", default="README.md")
    site.add_argument("--results", default="results.json")
    site.add_argument("--citation", default="CITATION.cff")
    site.add_argument(
        "--assets",
        nargs="*",
        default=DEFAULT_ASSETS,
        help="files or directories to copy",
    )
    site.add_argument("--repo", help="GitHub owner/name, for links")
    site.add_argument("--data-url", help="where the logs and data are published")

    args = parser.parse_args()
    if args.command == "readme":
        update_readme(Leaderboard.load(args.results).markdown(), args.readme)
    else:
        out = build(
            out=args.out,
            readme=args.readme,
            results=args.results,
            citation=args.citation,
            assets=args.assets,
            repo=args.repo,
            data_url=args.data_url,
        )
        print(f"Wrote {out / 'index.html'}")
