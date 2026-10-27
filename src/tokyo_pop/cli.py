"""Command line entry point: ``tokyo-pop update`` / ``tokyo-pop query``."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import db, pipeline
from .http import PoliteSession


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tokyo-pop", description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    sub = parser.add_subparsers(dest="command", required=True)

    update = sub.add_parser("update", help="fetch and load any new monthly releases")
    update.add_argument("--force", action="store_true", help="reprocess loaded releases")

    query = sub.add_parser("query", help="run SQL against the analytical views")
    query.add_argument("sql")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.command == "update":
        loaded = pipeline.run(PoliteSession(), args.data_dir, force=args.force)
        print(f"loaded {len(loaded)} new release(s)", *(f"  {r.as_of}" for r in loaded), sep="\n")
    elif args.command == "query":
        print(db.connect(args.data_dir).sql(args.sql))
    return 0


if __name__ == "__main__":
    sys.exit(main())
