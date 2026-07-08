#!/usr/bin/env python
"""Exporte le dataset d'entraînement depuis SQLite."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from app import app
from models import Article, db

DEFAULT_OUT = Path(__file__).resolve().parent / "data" / "dataset_entrainement.csv"


def export_dataset(output: Path, include_annote: bool = True) -> int:
    statuses = ["valide"]
    if include_annote:
        statuses.append("annote")

    with app.app_context():
        rows = (
            Article.query.filter(
                Article.status.in_(statuses),
                Article.category_id.isnot(None),
            )
            .order_by(Article.id.asc())
            .all()
        )

        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["titre", "contenu_nettoye", "categorie"])
            for art in rows:
                writer.writerow(
                    [
                        art.title,
                        art.content_clean,
                        art.category.name if art.category else "",
                    ]
                )
        return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export dataset NLP Projet 5")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUT,
        help="Fichier CSV de sortie",
    )
    parser.add_argument(
        "--valide-only",
        action="store_true",
        help="Exporter uniquement les articles validés",
    )
    args = parser.parse_args()
    n = export_dataset(args.output, include_annote=not args.valide_only)
    print(f"Exporté {n} articles -> {args.output}")


if __name__ == "__main__":
    main()
