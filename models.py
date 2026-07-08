from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def utc_now() -> datetime:
    """Datetime naive UTC (compatible PostgreSQL TIMESTAMP WITHOUT TIME ZONE)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class MediaSource(db.Model):
    __tablename__ = "media_sources"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    base_url = db.Column(db.String(255), nullable=False)
    method = db.Column(db.String(50), nullable=False)
    enabled = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now)

    articles = db.relationship("Article", back_populates="source")


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    examples = db.Column(db.Text, nullable=True)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now)


class Article(db.Model):
    __tablename__ = "articles"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    content_raw = db.Column(db.Text, nullable=False)
    content_clean = db.Column(db.Text, nullable=False)
    url = db.Column(db.String(700), unique=True, nullable=False)
    source_id = db.Column(db.Integer, db.ForeignKey("media_sources.id"), nullable=False)
    published_at = db.Column(db.DateTime, nullable=True)
    author = db.Column(db.String(255), nullable=True)
    site_section = db.Column(db.String(255), nullable=True)
    collected_at = db.Column(
        db.DateTime, default=utc_now, nullable=False
    )
    content_hash = db.Column(db.String(64), nullable=False, index=True)
    title_norm = db.Column(db.String(500), nullable=False, index=True)
    status = db.Column(db.String(30), default="non_annote", nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)
    annotator = db.Column(db.String(120), nullable=True)
    annotation_comment = db.Column(db.Text, nullable=True)
    annotated_at = db.Column(db.DateTime, nullable=True)
    near_duplicate_of_id = db.Column(db.Integer, db.ForeignKey("articles.id"), nullable=True)

    source = db.relationship("MediaSource", back_populates="articles")
    category = db.relationship("Category")
    near_duplicate_of = db.relationship("Article", remote_side=[id])


class ScrapeLog(db.Model):
    __tablename__ = "scrape_logs"

    id = db.Column(db.Integer, primary_key=True)
    source_code = db.Column(db.String(50), nullable=False, index=True)
    url = db.Column(db.String(700), nullable=True)
    level = db.Column(db.String(20), default="error", nullable=False)
    motif = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime, default=utc_now, nullable=False
    )


class CollectionRun(db.Model):
    __tablename__ = "collection_runs"

    id = db.Column(db.Integer, primary_key=True)
    started_at = db.Column(
        db.DateTime, default=utc_now, nullable=False
    )
    finished_at = db.Column(db.DateTime, nullable=True)
    sources = db.Column(db.String(255), nullable=False)
    added = db.Column(db.Integer, default=0)
    skipped = db.Column(db.Integer, default=0)
    errors = db.Column(db.Integer, default=0)
    report = db.Column(db.Text, nullable=True)
