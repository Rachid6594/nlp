"""Nettoyage de contenu et détection de doublons."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from difflib import SequenceMatcher

from bs4 import BeautifulSoup

NOISE_PATTERNS = [
    r"(?im)^\s*lire aussi\s*:?.*$",
    r"(?im)^\s*à lire aussi\s*:?.*$",
    r"(?im)^\s*voir aussi\s*:?.*$",
    r"(?im)^\s*partage[rz]? (cet|sur).*$",
    r"(?im)^\s*suivez[- ]nous.*$",
    r"(?im)^\s*newsletter.*$",
    r"(?im)^\s*publicité\s*$",
    r"(?im)^\s*commentaire[s]?\s*$",
]


def strip_html(html_or_text: str) -> str:
    if not html_or_text:
        return ""
    soup = BeautifulSoup(html_or_text, "lxml")
    for tag in soup(["script", "style", "noscript", "iframe", "form", "nav", "aside", "footer"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    return text


def normalize_whitespace(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_article_text(raw_html_or_text: str) -> str:
    """Nettoyage léger : conserve le texte naturel (accents, ponctuation).

    Pas de suppression de stopwords ni lemmatisation (réservé à la Partie II).
    """
    text = strip_html(raw_html_or_text)
    for pattern in NOISE_PATTERNS:
        text = re.sub(pattern, "", text)
    return normalize_whitespace(text)


def normalize_title(title: str) -> str:
    if not title:
        return ""
    title = unicodedata.normalize("NFKD", title)
    title = "".join(c for c in title if not unicodedata.combining(c))
    title = title.lower()
    title = re.sub(r"[^a-z0-9\s]", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def content_fingerprint(text: str) -> str:
    normalized = normalize_whitespace(text).lower()
    normalized = re.sub(r"\s+", " ", normalized)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def text_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    # Comparer sur préfixes pour rester rapide sur longs articles
    a_cmp = a[:4000]
    b_cmp = b[:4000]
    return SequenceMatcher(None, a_cmp, b_cmp).ratio()
