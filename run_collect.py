#!/usr/bin/env python
"""Collecte en ligne de commande (sans interface web)."""
from __future__ import annotations

import argparse

from app import app
from collector import collect_sources
from config import MEDIA_SOURCES


def main() -> None:
    parser = argparse.ArgumentParser(description="Collecte d'articles de presse BF")
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=sorted(MEDIA_SOURCES.keys()),
        default=sorted(MEDIA_SOURCES.keys()),
        help="Codes sources (défaut: toutes)",
    )
    parser.add_argument("--limit", type=int, default=50, help="Articles max par source")
    parser.add_argument(
        "--pages",
        type=int,
        default=5,
        help="Pages RSS historiques WordPress (?paged=N)",
    )
    args = parser.parse_args()

    with app.app_context():
        run = collect_sources(
            args.sources, limit_per_source=args.limit, max_pages=args.pages
        )
        print(f"Ajoutés={run.added} Ignorés={run.skipped} Erreurs={run.errors}")
        print(run.report or "")


if __name__ == "__main__":
    main()
