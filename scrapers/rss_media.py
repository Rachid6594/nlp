"""Base RSS + complément HTML pour médias WordPress/SPIP."""
from __future__ import annotations

from typing import Iterable, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import feedparser
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


def _paged_feed_url(rss_url: str, page: int) -> str:
    """Construit l'URL RSS paginée (WordPress: ?paged=N)."""
    if page <= 1:
        return rss_url
    parsed = urlparse(rss_url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    query["paged"] = [str(page)]
    new_query = urlencode(query, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


class RssHtmlScraper:
    """Stratégie : RSS pour découvrir (y compris pages historiques), HTML si besoin."""

    code: str = ""
    name: str = ""
    base_url: str = ""
    rss_url: str = ""
    content_selectors: list[str] = [
        ".entry-content",
        ".td-post-content",
        ".post-content",
        ".article_content",
        "article",
    ]
    title_selectors: list[str] = ["h1.entry-title", "h1"]
    extra_delay: float = 0.0
    min_rss_content_length: int = 800
    # Nombre max de pages RSS historiques (WordPress ?paged=)
    supports_rss_pagination: bool = True
    max_feed_pages: int = 10

    def __init__(self, client: HttpClient | None = None):
        self.client = client or HttpClient()

    def _parse_single_feed(self, feed_url: str) -> list[dict]:
        resp = self.client.get(feed_url, extra_delay=self.extra_delay)
        feed = feedparser.parse(resp.content)
        items = []
        for entry in feed.entries:
            content = ""
            if getattr(entry, "content", None):
                content = entry.content[0].value
            elif getattr(entry, "summary", None):
                content = entry.summary
            tags = []
            for t in getattr(entry, "tags", []) or []:
                term = getattr(t, "term", None)
                if term:
                    tags.append(term)
            link = clean_url(getattr(entry, "link", "") or "")
            if not link:
                continue
            items.append(
                {
                    "title": getattr(entry, "title", "") or "",
                    "link": link,
                    "published": parse_date(
                        getattr(entry, "published", None)
                        or getattr(entry, "updated", None)
                    ),
                    "author": getattr(entry, "author", None),
                    "content": content,
                    "section": tags[0] if tags else None,
                }
            )
        return items

    def _parse_feed(self, limit: int = 40, max_pages: int | None = None) -> list[dict]:
        """Agrège plusieurs pages RSS pour remonter plus loin dans le temps."""
        pages = max_pages if max_pages is not None else self.max_feed_pages
        if not self.supports_rss_pagination:
            pages = 1

        collected: list[dict] = []
        seen_urls: set[str] = set()

        for page in range(1, max(1, pages) + 1):
            feed_url = _paged_feed_url(self.rss_url, page)
            try:
                batch = self._parse_single_feed(feed_url)
            except Exception:
                break
            if not batch:
                break

            new_in_page = 0
            for item in batch:
                if item["link"] in seen_urls:
                    continue
                seen_urls.add(item["link"])
                collected.append(item)
                new_in_page += 1
                if len(collected) >= limit:
                    return collected

            if new_in_page == 0:
                break
            if len(batch) < 3 and page > 1:
                break

        return collected

    def fetch_html_article(self, url: str) -> tuple[str, str, Optional[str], Optional[str]]:
        resp = self.client.get(url, extra_delay=self.extra_delay)
        soup = BeautifulSoup(resp.text, "lxml")
        title = select_first_text(soup, self.title_selectors)
        if not title:
            title = extract_meta(soup, "og:title") or ""
        content_raw = extract_content_html(soup, self.content_selectors)
        return title, content_raw, author_from_soup(soup), category_from_soup(soup)

    def _rss_text_length(self, html_content: str) -> int:
        return len(BeautifulSoup(html_content or "", "lxml").get_text(" ", strip=True))

    def collect(self, limit: int = 30, max_pages: int | None = None) -> Iterable[ScrapedArticle]:
        for item in self._parse_feed(limit=limit, max_pages=max_pages):
            url = item["link"]
            title = item["title"]
            content_raw = item["content"] or ""
            author = item["author"]
            section = item["section"]
            published = item["published"]

            need_html = self._rss_text_length(content_raw) < self.min_rss_content_length
            if need_html:
                html_title, html_content, html_author, html_section = self.fetch_html_article(url)
                if html_content:
                    content_raw = html_content
                if html_title and (not title or len(html_title) > 5):
                    title = html_title
                author = author or html_author
                section = section or html_section

            yield ScrapedArticle(
                title=(title or "").strip(),
                content_raw=content_raw,
                url=url,
                source_code=self.code,
                published_at=published,
                author=author,
                site_section=section,
            )


class AibScraper(RssHtmlScraper):
    code = "aib"
    name = "AIB"
    base_url = "https://www.aib.media/"
    rss_url = "https://www.aib.media/feed/"
    content_selectors = [".td-post-content", ".entry-content", "article"]
    min_rss_content_length = 1200


class LefasoScraper(RssHtmlScraper):
    code = "lefaso"
    name = "Lefaso.net"
    base_url = "https://lefaso.net/"
    rss_url = "https://lefaso.net/spip.php?page=backend"
    content_selectors = [".article_content", "#content", "article"]
    title_selectors = ["h1.entry-title", "h1"]
    min_rss_content_length = 1500
    # SPIP backend : déjà ~80-90 entrées, pagination WordPress non applicable
    supports_rss_pagination = False


class Burkina24Scraper(RssHtmlScraper):
    code = "burkina24"
    name = "Burkina24"
    base_url = "https://burkina24.com/"
    rss_url = "https://burkina24.com/feed/"
    content_selectors = [".entry-content", ".post-content", "article"]
    min_rss_content_length = 800


class FasoActuScraper(RssHtmlScraper):
    code = "fasoactu"
    name = "Faso Actu"
    base_url = "https://faso-actu.info/"
    rss_url = "https://faso-actu.info/feed/"
    content_selectors = [".entry-content", "article.post", "article"]
    title_selectors = ["h1.entry-title", "h1"]
    extra_delay = 10.0  # robots.txt Crawl-delay: 10
    min_rss_content_length = 800
    max_feed_pages = 5  # délai 10s : limiter les pages


class FasozineScraper(RssHtmlScraper):
    code = "fasozine"
    name = "FasoZine"
    base_url = "https://fasozine.com/"
    rss_url = "https://fasozine.com/feed/"
    content_selectors = [".entry-content", "article", ".post-content"]
    title_selectors = ["h1.entry-title", "h1"]
    min_rss_content_length = 800


class Ouaga24Scraper(RssHtmlScraper):
    code = "ouaga24"
    name = "Ouaga24"
    base_url = "https://ouaga24.com/"
    rss_url = "https://ouaga24.com/feed/"
    content_selectors = [
        ".td-post-content",
        ".entry-content",
        ".tdb_single_content",
        "article",
        "#content",
    ]
    title_selectors = ["h1.entry-title", "h1.tdb-title-text", "h1"]
    min_rss_content_length = 800


class LaborpresseScraper(RssHtmlScraper):
    code = "laborpresse"
    name = "Laborpresse"
    base_url = "https://www.laborpresse.net/"
    rss_url = "https://www.laborpresse.net/feed/"
    content_selectors = [".entry-content", ".post-content", "article", "#content"]
    title_selectors = ["h1.entry-title", "h1"]
    min_rss_content_length = 600
