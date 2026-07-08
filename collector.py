"""Orchestrateur de collecte : scraping, dédoublonnage, journalisation."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from config import MIN_CONTENT_LENGTH, NEAR_DUPLICATE_THRESHOLD
from cleaning import clean_article_text, content_fingerprint, normalize_title, text_similarity
from models import Article, CollectionRun, MediaSource, ScrapeLog, db
from scrapers import SCRAPERS, get_scraper
from scrapers.base import CollectionReport
from scrapers.http_client import HttpClient

logger = logging.getLogger(__name__)


def _sanitize_text(value: str | None) -> str:
    if not value:
        return ""
    # PostgreSQL rejette le caractère NUL (\x00) dans les champs texte
    return value.replace("\x00", "")


def _naive_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _prepare_article_fields(scraped) -> dict:
    title = _sanitize_text((scraped.title or "").strip())[:500]
    content_raw = _sanitize_text(scraped.content_raw or "")
    content_clean = _sanitize_text(clean_article_text(content_raw))
    return {
        "title": title,
        "content_raw": content_raw,
        "content_clean": content_clean,
        "url": _sanitize_text(scraped.url)[:700],
        "author": _sanitize_text(scraped.author)[:255] if scraped.author else None,
        "site_section": _sanitize_text(scraped.site_section)[:255]
        if scraped.site_section
        else None,
        "published_at": _naive_utc(scraped.published_at),
    }


def log_error(source_code: str, motif: str, url: str | None = None) -> None:
    db.session.rollback()
    db.session.add(
        ScrapeLog(source_code=source_code, url=url, level="error", motif=motif)
    )
    db.session.commit()


def find_near_duplicate(content_clean: str, exclude_url: str | None = None) -> Article | None:
    # Comparer aux articles récents pour rester raisonnable en perf
    candidates = (
        Article.query.filter(Article.status != "rejete")
        .order_by(Article.id.desc())
        .limit(300)
        .all()
    )
    best = None
    best_score = 0.0
    for art in candidates:
        if exclude_url and art.url == exclude_url:
            continue
        score = text_similarity(content_clean, art.content_clean)
        if score > best_score:
            best_score = score
            best = art
    if best and best_score >= NEAR_DUPLICATE_THRESHOLD:
        return best
    return None


def persist_article(scraped, source: MediaSource) -> tuple[str, Article | None]:
    """Retourne (statut, article) où statut ∈ added|skipped|error|incomplete|duplicate.

    Politique corpus :
    - On ignore uniquement l'URL déjà connue (recollecte du même lien).
    - Les repris / quasi-doublons de contenu sont quand même enregistrés
      (statut « doublon ») pour grossir le jeu d'annotation / d'entraînement.
    """
    title = (scraped.title or "").strip()
    if not title:
        return "error", None

    fields = _prepare_article_fields(scraped)
    title = fields["title"]
    if not title:
        return "error", None

    # Seul cas vraiment inutile : même URL déjà connue
    if Article.query.filter_by(url=fields["url"]).first():
        return "skipped", None

    content_clean = fields["content_clean"]
    if len(content_clean) < MIN_CONTENT_LENGTH:
        article = Article(
            title=title,
            content_raw=fields["content_raw"],
            content_clean=content_clean,
            url=fields["url"],
            source_id=source.id,
            published_at=fields["published_at"],
            author=fields["author"],
            site_section=fields["site_section"],
            content_hash=content_fingerprint(content_clean or title),
            title_norm=normalize_title(title)[:500],
            status="incomplet",
        )
        db.session.add(article)
        db.session.commit()
        return "incomplete", article

    fingerprint = content_fingerprint(content_clean)
    title_norm = normalize_title(title)[:500]

    # Marquer sans jeter : utile pour volume d'entraînement
    exact_content = Article.query.filter_by(content_hash=fingerprint).first()
    near = None if exact_content else find_near_duplicate(content_clean)
    if not near:
        same_title = Article.query.filter_by(title_norm=title_norm).first()
        if same_title and text_similarity(content_clean, same_title.content_clean) >= 0.85:
            near = same_title

    if exact_content or near:
        status = "doublon"
        ref = exact_content or near
        near_id = ref.id
        outcome = "duplicate"
    else:
        status = "non_annote"
        near_id = None
        outcome = "added"

    article = Article(
        title=title,
        content_raw=fields["content_raw"],
        content_clean=content_clean,
        url=fields["url"],
        source_id=source.id,
        published_at=fields["published_at"],
        author=fields["author"],
        site_section=fields["site_section"],
        content_hash=fingerprint,
        title_norm=title_norm,
        status=status,
        near_duplicate_of_id=near_id,
    )
    db.session.add(article)
    db.session.commit()
    return outcome, article


def collect_sources(
    source_codes: list[str],
    limit_per_source: int = 20,
    max_pages: int = 5,
) -> CollectionRun:
    """Collecte multi-sources.

    max_pages : nombre de pages RSS historiques WordPress (?paged=N)
    pour remonter plus loin que le flux récent (ignoré pour HTML pur / Lefaso).
    """
    client = HttpClient()
    run = CollectionRun(sources=",".join(source_codes), added=0, skipped=0, errors=0)
    db.session.add(run)
    db.session.commit()

    reports: list[CollectionReport] = []

    for code in source_codes:
        report = CollectionReport(source_code=code)
        source = MediaSource.query.filter_by(code=code).first()
        if not source:
            report.errors += 1
            report.messages.append(f"Source inconnue: {code}")
            log_error(code, "Source inconnue en base")
            reports.append(report)
            continue
        if not source.enabled:
            report.messages.append(f"Source désactivée: {code}")
            reports.append(report)
            continue
        if code not in SCRAPERS:
            report.errors += 1
            report.messages.append(f"Aucun scraper pour {code}")
            log_error(code, "Aucun scraper enregistré")
            reports.append(report)
            continue

        scraper = get_scraper(code, client=client)
        try:
            for scraped in scraper.collect(
                limit=limit_per_source, max_pages=max_pages
            ):
                try:
                    outcome, _ = persist_article(scraped, source)
                    if outcome == "added":
                        report.added += 1
                    elif outcome == "duplicate":
                        # Conservé en base (statut doublon) : compte comme ajouté au corpus
                        report.added += 1
                        report.messages.append(f"Quasi-doublon conservé: {scraped.url}")
                    elif outcome == "incomplete":
                        report.skipped += 1
                        report.messages.append(f"Contenu incomplet: {scraped.url}")
                    elif outcome == "skipped":
                        report.skipped += 1
                    else:
                        report.errors += 1
                        log_error(code, "Titre introuvable", scraped.url)
                except Exception as exc:  # noqa: BLE001
                    report.errors += 1
                    motif = f"Erreur persist: {exc}"
                    report.messages.append(motif)
                    log_error(code, motif, getattr(scraped, "url", None))
                    db.session.rollback()
        except Exception as exc:  # noqa: BLE001
            report.errors += 1
            motif = f"Échec collecte source: {exc}"
            report.messages.append(motif)
            log_error(code, motif)
            db.session.rollback()

        reports.append(report)
        run.added += report.added
        run.skipped += report.skipped
        run.errors += report.errors

    lines = []
    for r in reports:
        lines.append(
            f"[{r.source_code}] ajoutés={r.added} ignorés={r.skipped} erreurs={r.errors}"
        )
        lines.extend(f"  - {m}" for m in r.messages[:20])
    run.report = "\n".join(lines)
    run.finished_at = _naive_utc(datetime.now(timezone.utc))
    db.session.commit()
    return run
