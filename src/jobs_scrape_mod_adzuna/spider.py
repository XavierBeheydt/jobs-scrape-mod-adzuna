"""Collecteur Adzuna : agregateur d'offres, France et Suisse.

Adzuna publie une interface documentee, avec une cle d'application gratuite
obtenue par simple inscription -- **pas d'OAuth**, ce qui la rend compatible avec
la contrainte du projet. Elle couvre la France et la Suisse, entre autres.

Ce module remplit le role que ``jobs-scrape-mod-indeed`` ne peut pas tenir : une
couverture large et multi-employeurs, obtenue par un canal officiel plutot qu'en
contournant une protection.

**Les salaires estimes ne sont pas enregistres.** Adzuna complete les annonces
sans remuneration par une estimation issue de son propre modele, signalee par
``salary_is_predicted``. Ranger cette valeur dans le meme champ qu'un salaire
reellement annonce reviendrait a presenter une prediction comme un fait : le
module ne conserve que les montants effectivement publies.
"""

from __future__ import annotations

import os
from typing import Any

from jobs_scrape.loaders import clean_text, html_to_text, to_float, to_iso_date
from jobs_scrape.spiders import ApiJobSpider

BASE = "https://api.adzuna.com/v1/api/jobs"

# Adzuna renvoie les montants sans preciser la devise : elle se deduit du pays.
CURRENCIES = {
    "fr": "EUR", "ch": "CHF", "de": "EUR", "at": "EUR", "it": "EUR",
    "be": "EUR", "nl": "EUR", "es": "EUR", "gb": "GBP", "us": "USD",
}

LANGUAGES = {"fr": "fr", "ch": "fr", "de": "de", "at": "de", "it": "it"}

# ``contract_type`` vaut "permanent" ou "contract" ; ``contract_time`` vaut
# "full_time" ou "part_time". Les deux notions sont distinctes et cumulables.
CONTRACT_TYPES = {"permanent": "permanent", "contract": "contractor"}


class AdzunaSpider(ApiJobSpider):
    """Interroge l'API de recherche d'Adzuna.

    Exige ``ADZUNA_APP_ID`` et ``ADZUNA_APP_KEY`` dans l'environnement.
    L'inscription est gratuite : https://developer.adzuna.com/

    Arguments acceptes via ``-a`` :

    ``country``       code pays (``fr``, ``ch``…), defaut ``ch``
    ``what``          mots-cles
    ``where``         lieu de reference
    ``distance``      rayon autour de ``where``, en kilometres
    ``max_days_old``  age maximal des annonces, en jours
    ``category``      etiquette de categorie Adzuna
    """

    name = "adzuna"
    allowed_domains = ["api.adzuna.com"]
    method = "GET"
    page_size = 50            # maximum accepte par l'API
    start_page = 1            # Adzuna numerote ses pages a partir de 1

    def __init__(
        self,
        country: str = "ch",
        what: str | None = None,
        where: str | None = None,
        distance: str | int | None = None,
        max_days_old: str | int | None = None,
        category: str | None = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.country = str(country).lower()
        self.what = clean_text(what)
        self.where = clean_text(where)
        self.distance = int(distance) if distance else None
        self.max_days_old = int(max_days_old) if max_days_old else None
        self.category = clean_text(category)
        self.app_id = os.environ.get("ADZUNA_APP_ID", "")
        self.app_key = os.environ.get("ADZUNA_APP_KEY", "")
        self._total: int | None = None

    # Le numero de page fait partie du chemin chez Adzuna, pas des parametres :
    # ``build_request`` est donc redefini plus bas.
    endpoint = BASE

    # -- requete ----------------------------------------------------------

    def build_request(self, page: int):
        """Adzuna met le numero de page dans le chemin de l'URL."""
        from urllib.parse import urlencode

        from scrapy.http import Request

        url = f"{BASE}/{self.country}/search/{page}?{urlencode(self.query_params(page))}"
        return Request(
            url=url, method="GET", headers=self.headers(),
            callback=self.parse, meta={"page": page}, dont_filter=True,
        )

    def query_params(self, page: int) -> dict[str, Any]:
        params: dict[str, Any] = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "results_per_page": self.page_size,
            "content-type": "application/json",
        }
        if self.what:
            params["what"] = self.what
        if self.where:
            params["where"] = self.where
        if self.distance:
            params["distance"] = self.distance
        if self.max_days_old:
            params["max_days_old"] = self.max_days_old
        if self.category:
            params["category"] = self.category
        return params

    def extract_rows(self, response) -> list[dict]:
        data = response.json()
        if self._total is None:
            self._total = data.get("count")
            if self._total:
                self.logger.info("%s offre(s) correspondent a la recherche", self._total)
        return data.get("results") or []

    def has_next_page(self, response, rows: list, page: int) -> bool:
        if not rows:
            return False
        if not self._total:
            return len(rows) >= self.page_size
        return page * self.page_size < self._total

    # -- traduction -------------------------------------------------------

    def parse_row(self, row: dict, response) -> Any:
        location = row.get("location") or {}
        company = row.get("company") or {}
        category = row.get("category") or {}

        fields: dict[str, Any] = {
            "external_id": clean_text(str(row.get("id"))) if row.get("id") else None,
            "url": clean_text(row.get("redirect_url")),
            "apply_url": clean_text(row.get("redirect_url")),
            "title": clean_text(row.get("title")),
            # ``full_description`` n'est pas toujours fourni ; ``description``
            # est tronquee a 500 caracteres. On prend la plus complete.
            "description": html_to_text(row.get("full_description") or row.get("description")),
            "company": clean_text(company.get("display_name")),
            "location_raw": clean_text(location.get("display_name")),
            "country": self.country.upper(),
            "lat": to_float(row.get("latitude")),
            "lon": to_float(row.get("longitude")),
            "posted_at": to_iso_date(row.get("created")),
            "lang": LANGUAGES.get(self.country),
            "contract_type": _contract(row),
            "occupations": [tag] if (tag := clean_text(category.get("tag"))) else [],
        }

        # ``area`` va du plus large au plus fin : ["Suisse", "Geneve", "Geneve"].
        area = [clean_text(a) for a in (location.get("area") or []) if clean_text(a)]
        if area:
            fields["city"] = area[-1]
            if len(area) >= 2:
                fields["region"] = area[1]

        fields.update(self._salary(row))
        return self.new_item(**{k: v for k, v in fields.items() if v not in (None, "", [])})

    def _salary(self, row: dict) -> dict[str, Any]:
        """N'enregistre que les remunerations reellement annoncees.

        Adzuna complete les offres muettes par une estimation issue de son
        modele, signalee par ``salary_is_predicted``. La ranger dans le meme
        champ qu'un salaire publie presenterait une prediction comme un fait.
        """
        predicted = str(row.get("salary_is_predicted", "0")).lower() in {"1", "true"}
        if predicted:
            return {}
        low = to_float(row.get("salary_min"))
        high = to_float(row.get("salary_max"))
        if low is None and high is None:
            return {}
        return {
            "salary_min": low,
            "salary_max": high,
            "salary_currency": CURRENCIES.get(self.country),
        }


def _contract(row: dict) -> str | None:
    """Combine les deux notions distinctes exposees par Adzuna.

    ``contract_type`` dit si le poste est fixe ou sous contrat ;
    ``contract_time`` dit s'il est a temps plein ou partiel. Le champ
    ``contract_type`` du schema commun ne peut en porter qu'une : on privilegie
    la nature du contrat, plus discriminante, et on retombe sur la duree.
    """
    kind = clean_text(row.get("contract_type"))
    if kind:
        return CONTRACT_TYPES.get(kind.lower(), kind.lower())
    time = clean_text(row.get("contract_time"))
    return time.lower() if time else None
