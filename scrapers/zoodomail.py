"""Scraper Zoodomail | HTML Drupal (pas de RSS exploitable)."""
from __future__ import annotations

from typing import Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scrapers.base import ScrapedArticle
from scrapers.http_client import HttpClient
from scrapers.utils import (
    author_from_soup,
    category_from_soup,
    clean_url,
    extract_content_html,
    extract_meta,
    parse_date,
    select_first_text,
)


class ZoodomailScraper:
    code = "zoodomail"
    name = "Zoodomail"
    base_url = "https://www.zoodomail.com/"

    CONTENT_SELECTORS = [
        "article .node__content",
        "article",
        ".region-content",
        ".content",
    ]
    TITLE_SELECTORS = ["h1.page-title", "h1 span", "h1"]

    def __init__(self, client: HttpClient | None = None):
        self.client = client or HttpClient()

    def list_article_urls(self, limit: int = 40) -> list[str]:
        resp = self.client.get(self.base_url)
        soup = BeautifulSoup(resp.text, "lxml")
        urls: list[str] = []
        seen: set[str] = set()
        for a in soup.select('a[href*="/node/"]'):
            href = clean_url(urljoin(self.base_url, a["href"]))
            if "/node/" not in href or href in seen:
                continue
            # Ignorer les pages système éventuelles
            if href.rstrip("/").endswith("/node"):
                continue
            seen.add(href)
            urls.append(href)
            if len(urls) >= limit:
                break
        return urls

    def fetch_article(self, url: str) -> ScrapedArticle:
        url = clean_url(url)
        resp = self.client.get(url)
        soup = BeautifulSoup(resp.text, "lxml")
        title = select_first_text(soup, self.TITLE_SELECTORS)
        if not title:
            title = extract_meta(soup, "og:title") or ""
        content_raw = extract_content_html(soup, self.CONTENT_SELECTORS)
        published = parse_date(
            extract_meta(soup, "article:published_time", "og:published_time")
            or select_first_text(soup, ["time", ".submitted", ".node__meta"])
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
        # max_pages ignoré (HTML Drupal), compatibilité orchestrateur
        for url in self.list_article_urls(limit=limit):
            yield self.fetch_article(url)
