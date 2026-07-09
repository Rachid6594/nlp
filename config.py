"""Configuration centrale du projet de classification d'articles de presse."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "articles.db"
PROD_MODEL_DIR = BASE_DIR / "models" / "tfidf-svm-optimise"

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-nlp-projet5-uvbf-change-en-production")


def get_database_uri() -> str:
    """SQLite en local, PostgreSQL sur Render (variable DATABASE_URL)."""
    url = os.environ.get("DATABASE_URL")
    if url:
        # Render fournit postgres:// ; SQLAlchemy attend postgresql://
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DB_PATH.as_posix()}"


SQLALCHEMY_DATABASE_URI = get_database_uri()
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Respect des sites sources (académique)
USER_AGENT = (
    "NLPAcademicBot/1.0 (+UVBF-FDIA; projet-classification-presse; contact=etudiant)"
)
REQUEST_TIMEOUT = 25
REQUEST_DELAY_SECONDS = 1.5  # délai entre requêtes HTTP
MIN_CONTENT_LENGTH = 200  # contenu trop court => incomplet
NEAR_DUPLICATE_THRESHOLD = 0.92

DEFAULT_CATEGORIES = [
    ("Politique", "Vie institutionnelle, gouvernements, élections, partis, diplomatie."),
    ("Économie", "Finances, entreprises, commerce, agriculture commerciale, emploi."),
    ("Sport", "Compétitions sportives, clubs, athlètes, résultats."),
    ("Culture", "Arts, musique, cinéma, patrimoine, festivals, médias culturels."),
    ("Santé", "Hôpitaux, épidémies, campagnes sanitaires, médicaments."),
    ("Éducation", "Écoles, universités, examens, formation, recherche académique."),
    ("Société", "Vie quotidienne, solidarité, religion, faits divers sociaux."),
    ("Sécurité", "Défense, terrorisme, FDS, criminalité, sécurité publique."),
]

MEDIA_SOURCES = {
    "rtb": {
        "name": "RTB",
        "base_url": "https://www.rtb.bf/",
        "method": "html",
        "enabled": True,
    },
    "aib": {
        "name": "AIB",
        "base_url": "https://www.aib.media/",
        "rss_url": "https://www.aib.media/feed/",
        "method": "rss+html",
        "enabled": True,
    },
    "lefaso": {
        "name": "Lefaso.net",
        "base_url": "https://lefaso.net/",
        "rss_url": "https://lefaso.net/spip.php?page=backend",
        "method": "rss+html",
        "enabled": True,
        "director": "Cyriaque PARE",
    },
    "burkina24": {
        "name": "Burkina24",
        "base_url": "https://burkina24.com/",
        "rss_url": "https://burkina24.com/feed/",
        "method": "rss+html",
        "enabled": True,
        "director": "Jérôme LANKOANDE",
    },
    "fasoactu": {
        "name": "Faso Actu (info)",
        "base_url": "https://faso-actu.info/",
        "rss_url": "https://faso-actu.info/feed/",
        "method": "rss+html",
        "enabled": True,
        "crawl_delay": 10,  # robots.txt Crawl-delay: 10
        "note": "faso-actu.net redirige vers faso-actu.info",
    },
    "fasozine": {
        "name": "FasoZine",
        "base_url": "https://fasozine.com/",
        "rss_url": "https://fasozine.com/feed/",
        "method": "rss+html",
        "enabled": True,
        "director": "Morin YAMONGBE",
    },
    "ouaga24": {
        "name": "Ouaga24",
        "base_url": "https://ouaga24.com/",
        "rss_url": "https://ouaga24.com/feed/",
        "method": "rss+html",
        "enabled": True,
        "director": "Emile ILBOUDO dit Scipion",
    },
    "zoodomail": {
        "name": "Zoodomail",
        "base_url": "https://www.zoodomail.com/",
        "method": "html",
        "enabled": True,
        "director": "Paul TIEMTORE",
    },
    "laborpresse": {
        "name": "Laborpresse",
        "base_url": "https://www.laborpresse.net/",
        "rss_url": "https://www.laborpresse.net/feed/",
        "method": "rss+html",
        "enabled": True,
        "director": "Jean KY",
    },
}

UNAVAILABLE_SOURCES = {
    "fasoactu_com": {
        "name": "fasoactu.com",
        "base_url": "https://www.fasoactu.com/",
        "director": "Salif SOULAMA",
        "reason": "Page vide / non exploitable au moment du test",
    },
    "fasonews": {
        "name": "fasonews.com",
        "base_url": "https://www.fasonews.com/",
        "director": "Azize OUEDRAOGO",
        "reason": "Site en redirection lander / non rédactionnel",
    },
}
