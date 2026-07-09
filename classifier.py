"""Chargement et prédiction du modèle TF-IDF + SVM (étape 6)."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from config import PROD_MODEL_DIR


class ClassifierNotReadyError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _load_artifacts() -> tuple[Any, list[str], dict[str, Any]]:
    pipeline_path = PROD_MODEL_DIR / "pipeline.joblib"
    metadata_path = PROD_MODEL_DIR / "metadata.json"
    if not pipeline_path.is_file():
        raise ClassifierNotReadyError(
            f"Modèle introuvable : {pipeline_path}. "
            "Exécutez la section 7 du notebook d'entraînement."
        )
    model = joblib.load(pipeline_path)
    metadata: dict[str, Any] = {}
    if metadata_path.is_file():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    labels = metadata.get("labels") or []
    return model, labels, metadata


def model_status() -> dict[str, Any]:
    """État du modèle pour l'interface (disponible, métriques, chemins)."""
    pipeline_path = PROD_MODEL_DIR / "pipeline.joblib"
    metadata_path = PROD_MODEL_DIR / "metadata.json"
    if not pipeline_path.is_file():
        return {
            "ready": False,
            "path": str(pipeline_path),
            "message": "Modèle non trouvé. Lancez le notebook (section 7) pour générer pipeline.joblib.",
        }
    meta: dict[str, Any] = {}
    if metadata_path.is_file():
        meta = json.loads(metadata_path.read_text(encoding="utf-8"))
    return {
        "ready": True,
        "path": str(pipeline_path),
        "modele": meta.get("modele", "TF-IDF + SVM"),
        "best_params": meta.get("best_params", {}),
        "test_f1_weighted": meta.get("test_f1_weighted"),
        "test_accuracy": meta.get("test_accuracy"),
        "n_total": meta.get("n_total"),
        "labels": meta.get("labels", []),
    }


def build_input_text(titre: str, contenu: str) -> str:
    return f"{titre.strip()} {contenu.strip()}".strip()


def predict_categories(texte: str, top_k: int | None = None) -> dict[str, Any]:
    """Retourne la catégorie prédite et les scores de confiance par classe."""
    if not texte or len(texte.strip()) < 20:
        raise ValueError("Le texte est trop court (minimum ~20 caractères).")

    model, labels, metadata = _load_artifacts()
    if not labels:
        labels = list(metadata.get("label2id", {}).keys())

    scores = model.decision_function([texte])[0]
    exp_scores = np.exp(scores - np.max(scores))
    probs = exp_scores / exp_scores.sum()

    ranking = sorted(
        [
            {"label": labels[i], "score": float(probs[i]), "percent": round(float(probs[i]) * 100, 2)}
            for i in range(len(labels))
        ],
        key=lambda x: x["score"],
        reverse=True,
    )
    if top_k is not None:
        ranking = ranking[:top_k]

    best = ranking[0]
    return {
        "prediction": best["label"],
        "confidence": best["percent"],
        "scores": ranking,
        "modele": metadata.get("modele", "TF-IDF + SVM"),
    }
