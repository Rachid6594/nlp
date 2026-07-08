"""Utilitaires d'extraction HTML / dates communes aux scrapers."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from dateutil import parser as date_parser


NOISE_SELECTORS = [
    "script",
    "style",
    "noscript",
    "iframe",
    "nav",
    "aside",
    "footer",
    "form",
    ".sharedaddy",
    ".share",
    ".social",
    ".comments",
    "#comments",
    ".related-posts",
    ".jp-relatedposts",
    ".advertisement",
    ".ads",
]


def parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return date_parser.parse(value, fuzzy=True)
    except (ValueError, OverflowError, TypeError):
        return None


def absolute_url(base: str, href: str) -> str:
    return urljoin(base, href)


def clean_url(url: str) -> str:
    return url.split("#")[0].split("?")[0].rstrip("/")


def extract_meta(soup: BeautifulSoup, *keys: str) -> Optional[str]:
    for key in keys:
        tag = soup.find("meta", property=key) or soup.find("meta", attrs={"name": key})
        if tag and tag.get("content"):
            return tag["content"].strip()
    return None


def select_first_text(soup: BeautifulSoup, selectors: list[str]) -> Optional[str]:
    for sel in selectors:
        node = soup.select_one(sel)
        if node:
            text = node.get_text(" ", strip=True)
            if text:
                return text
    return None


def extract_content_html(soup: BeautifulSoup, selectors: list[str]) -> str:
    for sel in selectors:
        node = soup.select_one(sel)
        if not node:
            continue
        clone = BeautifulSoup(str(node), "lxml")
        root = clone.body or clone
        for noise in root.select(", ".join(NOISE_SELECTORS)):
            noise.decompose()
        text = root.get_text("\n", strip=True)
        if len(text) >= 120:
            return str(root)
    # fallback: article / main
    for tag_name in ("article", "main"):
        node = soup.find(tag_name)
        if node:
            return str(node)
    return ""


def discover_wp_dated_links(soup: BeautifulSoup, base_url: str) -> list[str]:
    """URLs WordPress du type /YYYY/MM/DD/slug/."""
    pattern = re.compile(r"/\d{4}/\d{2}/\d{2}/[^/#?]+/?$")
    found: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = absolute_url(base_url, a["href"])
        href = clean_url(href)
        if pattern.search(href) and href not in seen and base_url.rstrip("/") in href:
            seen.add(href)
            found.append(href)
    return found


def category_from_soup(soup: BeautifulSoup) -> Optional[str]:
    for rel in soup.select('a[rel="category tag"], .cat-links a, .entry-categories a, .td-post-category'):
        text = rel.get_text(" ", strip=True)
        if text:
            return text
    crumbs = soup.select(".breadcrumb a, .breadcrumbs a")
    if len(crumbs) >= 2:
        return crumbs[-1].get_text(" ", strip=True)
    return None


def author_from_soup(soup: BeautifulSoup) -> Optional[str]:
    meta = extract_meta(soup, "author", "article:author")
    if meta:
        return meta
    node = soup.select_one(".author, .byline, .td-post-author-name a, .entry-author a, .auteur")
    if node:
        return node.get_text(" ", strip=True)
    return None
