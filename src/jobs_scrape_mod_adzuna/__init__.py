"""Collecteur jobs-scrape pour Adzuna (agregateur, France et Suisse)."""

from jobs_scrape.source import SourceMeta

from jobs_scrape_mod_adzuna.spider import AdzunaSpider

__version__ = "0.1.0"

SOURCE = SourceMeta(
    name="adzuna",
    spider=AdzunaSpider,
    access="api",
    country="CH/FR",
    domains=("api.adzuna.com",),
    description="Agregateur d'offres, couverture France et Suisse",
    requires_env=("ADZUNA_APP_ID", "ADZUNA_APP_KEY"),
    notes=(
        "API officielle documentee, cle gratuite obtenue par inscription "
        "(pas d'OAuth). Substitut fonctionnel du module 'indeed', inatteignable. "
        "Les salaires estimes par le modele d'Adzuna ne sont pas enregistres : "
        "seuls les montants reellement annonces le sont."
    ),
)

__all__ = ["SOURCE", "AdzunaSpider"]
