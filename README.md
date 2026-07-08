# Projet NLP 5 | Classification automatique d'articles de presse (Partie I)

Application Flask pour la **collecte**, le **nettoyage**, l'**annotation** et l'**export** d'un corpus d'articles issus de médias burkinabè.

## Sources actives

| Code | Média | Méthode |
|------|-------|---------|
| `rtb` | RTB | HTML |
| `aib` | AIB | RSS + HTML |
| `lefaso` | Lefaso.net | RSS + HTML |
| `burkina24` | Burkina24 | RSS + HTML |
| `fasoactu` | Faso Actu (faso-actu.info) | RSS + HTML (Crawl-delay 10 s) |
| `fasozine` | FasoZine | RSS + HTML |
| `ouaga24` | Ouaga24 | RSS + HTML |
| `zoodomail` | Zoodomail | HTML (Drupal) |
| `laborpresse` | Laborpresse | RSS + HTML |

Non exploitables pour l'instant : `fasoactu.com` (page vide), `fasonews.com` (lander). `faso-actu.net` redirige vers `faso-actu.info`.

Chaque média a un scraper indépendant dans `scrapers/`.

## Installation

```bash
cd nlp
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Lancer l'interface

```bash
python app.py
```

Ouvrir [http://127.0.0.1:5000](http://127.0.0.1:5000)

## Collecte en ligne de commande

```bash
# Historique RSS : 5 pages x jusqu'à 50 articles / source
python run_collect.py --sources aib burkina24 fasozine ouaga24 laborpresse --limit 50 --pages 5
python run_collect.py --sources rtb --limit 20
```

Les sites WordPress exposent souvent `/feed/?paged=2`, `/feed/?paged=3`, etc. L'option `--pages` active cette pagination pour remonter plus loin que le flux du jour.

## Workflow Partie I

1. **Sources** : activer / désactiver les médias
2. **Collecte** : découvrir les articles (RSS ou HTML), extraire, nettoyer, dedupliquer
3. **Catégories** : définir / ajuster les labels (Politique, Économie, …)
4. **Annotation** : étiqueter article par article (valider, rejeter, incomplet, doublon)
5. **Export CSV** : colonnes `titre`, `contenu_nettoye`, `categorie` (articles validés seulement)

## Statuts article

`non_annote` · `annote` · `valide` · `rejete` · `incomplet` · `doublon`

## Respect des sites

- User-Agent académique identifiable
- Consultation de `robots.txt`
- Délai entre requêtes (10 s pour Faso Actu)
- Usage pédagogque uniquement (UVBF / FDIA)

## Structure

```
nlp/
├── app.py              # Application Flask
├── collector.py        # Orchestrateur de collecte
├── cleaning.py         # Nettoyage + empreintes
├── config.py
├── models.py           # SQLAlchemy (SQLite local / PostgreSQL Render)
├── render.yaml         # Déploiement Render
├── runtime.txt
├── run_collect.py
├── scrapers/           # 1 connecteur par média
├── templates/
├── static/
└── data/articles.db    # créé au premier lancement
```

La lemmatisation / suppression de stopwords est **volontairement absente** du scraping : elle dépendra des vectorisations (Partie II).

## Déploiement sur Render

### Prérequis
- Compte [Render](https://render.com)
- Repo GitHub avec le projet poussé

### Option A : Blueprint (recommandé)
1. Render Dashboard → **New** → **Blueprint**
2. Connecter le repo GitHub
3. Render lit `render.yaml` et crée :
   - le **Web Service** Flask (Gunicorn)
   - la base **PostgreSQL**
4. Déployer → URL du type `https://presse-bf-nlp.onrender.com`

### Option B : Manuel
1. **New PostgreSQL** → copier l’**Internal Database URL**
2. **New Web Service** → repo Python
   - **Build** : `pip install -r requirements.txt`
   - **Start** : `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 300`
3. Variables d’environnement :
   - `DATABASE_URL` = URL Postgres (Render la fournit)
   - `SECRET_KEY` = chaîne aléatoire longue

### Base PostgreSQL gratuite alternative
Si Render ne propose plus Postgres gratuit sur ton compte, utilise [Neon](https://neon.tech) (gratuit) :
1. Créer une base sur Neon
2. Coller l’URL dans `DATABASE_URL` sur Render

### Local vs production
| Environnement | Base |
|---------------|------|
| Local (`python app.py`) | SQLite `data/articles.db` |
| Render | PostgreSQL via `DATABASE_URL` |

### Notes importantes
- La collecte peut durer plusieurs minutes : timeout Gunicorn fixé à **300 s**
- Sur le plan gratuit Render, le service **s’endort** après inactivité (1re requête lente)
- Le notebook CamemBERT reste **local** ou Colab (trop lourd pour le web service)
