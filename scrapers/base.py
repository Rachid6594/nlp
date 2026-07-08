from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ScrapedArticle:
    title: str
    content_raw: str
    url: str
    source_code: str
    published_at: Optional[datetime] = None
    author: Optional[str] = None
    site_section: Optional[str] = None
    extras: dict = field(default_factory=dict)


@dataclass
class CollectionReport:
    source_code: str
    added: int = 0
    skipped: int = 0
    errors: int = 0
    messages: list[str] = field(default_factory=list)
