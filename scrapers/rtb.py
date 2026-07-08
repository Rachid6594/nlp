"""Scraper RTB | HTML uniquement (pas de RSS exploitable)."""
from __future__ import annotations

from typing import Iterable

from bs4 import BeautifulSoup

from scrapers.base import ScrapedArticle
from scrapers.http_client import HttpClient
from scrapers.utils import (
    author_from_soup,
    category_from_soup,
    clean_url,
    discover_wp_dated_links,
    extract_content_html,
    extract_meta,
    parse_date,
    select_first_text,
)


class RtbScraper:
    code = "rtb"
    name = "RTB"
    base_url = "https://www.rtb.bf/"

    CONTENT_SELECTORS = [
        ".td-post-content",
        ".entry-content",
        ".post-content",
        "article .tdb_single_content",
        "article",
    ]
    TITLE_SELECTORS = [
        "h1.entry-title",
        "h1.tdb-title-text",
        "h1",
        "meta[property='og:title']",
    ]

    def __init__(self, client: HttpClient | None = None):
        self.client = client or HttpClient()

    def list_article_urls(self, limit: int = 40) -> list[str]:
        resp = self.client.get(self.base_url)
        soup = BeautifulSoup(resp.text, "lxml")
        urls = discover_wp_dated_links(soup, self.base_url)
        # Filtrer les JT / émissions purement vidéo trop courtes plus tard
        return urls[:limit]

    def fetch_article(self, url: str) -> ScrapedArticle:
        url = clean_url(url)
        resp = self.client.get(url)
        soup = BeautifulSoup(resp.text, "lxml")

        title = select_first_text(soup, ["h1.entry-title", "h1.tdb-title-text", "h1"])
        if not title:
            title = extract_meta(soup, "og:title") or ""
        content_raw = extract_content_html(soup, self.CONTENT_SELECTORS)
        published = parse_date(
            extract_meta(soup, "article:published_time", "og:published_time")
            or select_first_text(soup, ["time", ".td-post-date", ".entry-date"])
        )
        return ScrapedArticle(
            title=title.strip(),
            content_raw=content_raw,
            url=url,
            source_code=self.code,
            published_at=published,
            author=author_from_soup(soup),
            site_section=category_from_soup(soup),
        )

    def collect(self, limit: int = 30, max_pages: int | None = None) -> Iterable[ScrapedArticle]:
        # max_pages ignoré (pas de RSS), conservé pour compatibilité orchestrateur
        for url in self.list_article_urls(limit=limit):
            yield self.fetch_article(url)
