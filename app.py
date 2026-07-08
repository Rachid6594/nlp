"""Application Flask | Partie I : collecte, annotation, export."""
from __future__ import annotations

import csv
import io
import math
from datetime import datetime, timezone

from flask import (
    Flask,
    Response,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from collector import collect_sources
from config import (
    DATA_DIR,
    DEFAULT_CATEGORIES,
    MEDIA_SOURCES,
    SECRET_KEY,
    SQLALCHEMY_DATABASE_URI,
    SQLALCHEMY_TRACK_MODIFICATIONS,
)
from models import Article, Category, CollectionRun, MediaSource, ScrapeLog, db, utc_now


def create_app() -> Flask:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    app = Flask(__name__)
    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = SQLALCHEMY_TRACK_MODIFICATIONS

    db.init_app(app)

    with app.app_context():
        db.create_all()
        seed_data()

    register_routes(app)
    return app


def seed_data() -> None:
    for code, meta in MEDIA_SOURCES.items():
        if not MediaSource.query.filter_by(code=code).first():
            db.session.add(
                MediaSource(
                    code=code,
                    name=meta["name"],
                    base_url=meta["base_url"],
                    method=meta["method"],
                    enabled=meta.get("enabled", True),
                )
            )
    for name, description in DEFAULT_CATEGORIES:
        if not Category.query.filter_by(name=name).first():
            db.session.add(Category(name=name, description=description, active=True))
    db.session.commit()


def register_routes(app: Flask) -> None:
    @app.route("/")
    def index():
        stats = {
            "total": Article.query.count(),
            "non_annote": Article.query.filter_by(status="non_annote").count(),
            "annote": Article.query.filter_by(status="annote").count(),
            "valide": Article.query.filter_by(status="valide").count(),
            "rejete": Article.query.filter_by(status="rejete").count(),
            "incomplet": Article.query.filter_by(status="incomplet").count(),
            "doublon": Article.query.filter_by(status="doublon").count(),
        }
        sources = MediaSource.query.order_by(MediaSource.name).all()
        last_runs = CollectionRun.query.order_by(CollectionRun.id.desc()).limit(5).all()
        return render_template("index.html", stats=stats, sources=sources, last_runs=last_runs)

    @app.route("/sources", methods=["GET", "POST"])
    def sources():
        if request.method == "POST":
            for source in MediaSource.query.all():
                source.enabled = request.form.get(f"enabled_{source.code}") == "on"
            db.session.commit()
            flash("Sources mises à jour.", "success")
            return redirect(url_for("sources"))
        from config import MEDIA_SOURCES, UNAVAILABLE_SOURCES

        sources = MediaSource.query.order_by(MediaSource.name).all()
        meta = {
            code: {
                "director": cfg.get("director"),
                "note": cfg.get("note"),
            }
            for code, cfg in MEDIA_SOURCES.items()
        }
        return render_template(
            "sources.html",
            sources=sources,
            source_meta=meta,
            unavailable=UNAVAILABLE_SOURCES,
        )

    @app.route("/collect", methods=["GET", "POST"])
    def collect():
        sources = MediaSource.query.order_by(MediaSource.name).all()
        if request.method == "POST":
            selected = request.form.getlist("sources")
            limit = int(request.form.get("limit", 40))
            max_pages = int(request.form.get("max_pages", 5))
            if not selected:
                flash("Sélectionnez au moins une source.", "warning")
                return redirect(url_for("collect"))
            run = collect_sources(
                selected, limit_per_source=limit, max_pages=max_pages
            )
            flash(
                f"Collecte terminée : ajoutés: {run.added}, ignorés: {run.skipped}, erreurs: {run.errors}",
                "success" if run.errors == 0 else "warning",
            )
            return redirect(url_for("collect_report", run_id=run.id))
        return render_template("collect.html", sources=sources)

    @app.route("/collect/report/<int:run_id>")
    def collect_report(run_id: int):
        run = CollectionRun.query.get_or_404(run_id)
        return render_template("collect_report.html", run=run)

    @app.route("/logs")
    def logs():
        items = ScrapeLog.query.order_by(ScrapeLog.id.desc()).limit(200).all()
        return render_template("logs.html", logs=items)

    @app.route("/categories", methods=["GET", "POST"])
    def categories():
        if request.method == "POST":
            action = request.form.get("action")
            if action == "create":
                name = (request.form.get("name") or "").strip()
                if not name:
                    flash("Le nom est obligatoire.", "warning")
                elif Category.query.filter_by(name=name).first():
                    flash("Cette catégorie existe déjà.", "warning")
                else:
                    db.session.add(
                        Category(
                            name=name,
                            description=request.form.get("description") or "",
                            examples=request.form.get("examples") or "",
                            active=True,
                        )
                    )
                    db.session.commit()
                    flash("Catégorie créée.", "success")
            elif action == "toggle":
                cat = Category.query.get_or_404(int(request.form["category_id"]))
                cat.active = not cat.active
                db.session.commit()
                flash(f"Catégorie « {cat.name} » mise à jour.", "success")
            elif action == "update":
                cat = Category.query.get_or_404(int(request.form["category_id"]))
                cat.description = request.form.get("description") or ""
                cat.examples = request.form.get("examples") or ""
                db.session.commit()
                flash("Description mise à jour.", "success")
            return redirect(url_for("categories"))
        cats = Category.query.order_by(Category.name).all()
        return render_template("categories.html", categories=cats)

    @app.route("/annotate")
    def annotate_list():
        status = request.args.get("status", "non_annote")
        source_id = request.args.get("source_id", type=int)
        page = max(1, request.args.get("page", 1, type=int))
        per_page = 20

        q = Article.query
        if status:
            q = q.filter_by(status=status)
        if source_id:
            q = q.filter_by(source_id=source_id)

        total = q.count()
        total_pages = max(1, math.ceil(total / per_page)) if total else 1
        if page > total_pages:
            page = total_pages

        articles = (
            q.order_by(Article.collected_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        sources = MediaSource.query.order_by(MediaSource.name).all()
        return render_template(
            "annotate_list.html",
            articles=articles,
            sources=sources,
            status=status,
            source_id=source_id,
            page=page,
            per_page=per_page,
            total=total,
            total_pages=total_pages,
        )

    @app.route("/annotate/<int:article_id>", methods=["GET", "POST"])
    def annotate(article_id: int):
        article = Article.query.get_or_404(article_id)
        categories = Category.query.filter_by(active=True).order_by(Category.name).all()

        if request.method == "POST":
            action = request.form.get("action")

            if action == "supprimer":
                nxt = (
                    Article.query.filter(
                        Article.status == "non_annote", Article.id != article.id
                    )
                    .order_by(Article.id.asc())
                    .first()
                )
                title = article.title[:80]
                # Détacher les références éventuelles vers cet article
                Article.query.filter_by(near_duplicate_of_id=article.id).update(
                    {"near_duplicate_of_id": None}
                )
                db.session.delete(article)
                db.session.commit()
                flash(f"Article supprimé : {title}", "success")
                if nxt:
                    return redirect(url_for("annotate", article_id=nxt.id))
                return redirect(url_for("annotate_list"))

            comment = (request.form.get("comment") or "").strip()
            article.annotation_comment = comment or None
            article.annotated_at = utc_now()

            if action == "valider":
                cat_id = request.form.get("category_id")
                if not cat_id:
                    flash("Choisissez une catégorie.", "warning")
                    return redirect(url_for("annotate", article_id=article.id))
                article.category_id = int(cat_id)
                article.status = "valide"
                flash("Article validé.", "success")
            elif action == "annoter":
                cat_id = request.form.get("category_id")
                if not cat_id:
                    flash("Choisissez une catégorie.", "warning")
                    return redirect(url_for("annotate", article_id=article.id))
                article.category_id = int(cat_id)
                article.status = "annote"
                flash("Article annoté.", "success")
            elif action == "rejeter":
                article.status = "rejete"
                flash("Article rejeté.", "success")
            elif action == "incomplet":
                article.status = "incomplet"
                flash("Article signalé incomplet.", "success")
            elif action == "doublon":
                article.status = "doublon"
                flash("Article signalé doublon.", "success")
            elif action == "passer":
                flash("Article ignoré pour le moment.", "info")
            db.session.commit()

            nxt = (
                Article.query.filter(
                    Article.status == "non_annote", Article.id != article.id
                )
                .order_by(Article.id.asc())
                .first()
            )
            if nxt and action != "passer":
                return redirect(url_for("annotate", article_id=nxt.id))
            if action == "passer":
                nxt = (
                    Article.query.filter(
                        Article.status == "non_annote", Article.id > article.id
                    )
                    .order_by(Article.id.asc())
                    .first()
                )
                if nxt:
                    return redirect(url_for("annotate", article_id=nxt.id))
            return redirect(url_for("annotate_list"))

        return render_template("annotate.html", article=article, categories=categories)

    @app.route("/articles")
    def articles():
        status = request.args.get("status")
        q = Article.query
        if status:
            q = q.filter_by(status=status)
        items = q.order_by(Article.id.desc()).limit(200).all()
        return render_template("articles.html", articles=items, status=status)

    @app.route("/export.csv")
    def export_csv():
        rows = (
            Article.query.filter_by(status="valide")
            .order_by(Article.id.asc())
            .all()
        )
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["titre", "contenu_nettoye", "categorie"])
        for art in rows:
            writer.writerow(
                [
                    art.title,
                    art.content_clean,
                    art.category.name if art.category else "",
                ]
            )
        output = buf.getvalue()
        return Response(
            output,
            mimetype="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": "attachment; filename=dataset_valide.csv"
            },
        )


app = create_app()

if __name__ == "__main__":
    import os

    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=debug, host="0.0.0.0", port=port)
