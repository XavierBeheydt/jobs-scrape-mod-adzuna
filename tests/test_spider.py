"""Tests du collecteur Adzuna.

La fixture est **synthetique** : elle reproduit le schema officiel
(``Adzuna::API::Response::Job``, releve sur ``api.adzuna.com/v1/api-docs`` le
2026-08-21) mais n'est pas une reponse enregistree, faute de cle d'API. Elle
couvre volontairement trois cas : une offre complete, une offre au salaire
**estime** par le modele d'Adzuna, et une offre minimale.
"""

import json
from pathlib import Path

import pytest
from jobs_scrape.testing import assert_usable, json_response

from jobs_scrape_mod_adzuna import SOURCE
from jobs_scrape_mod_adzuna.spider import AdzunaSpider, _contract

FIXTURE = Path(__file__).parent / "fixtures" / "search_page.json"
URL = "https://api.adzuna.com/v1/api/jobs/ch/search/1"


@pytest.fixture
def payload():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def spider():
    return AdzunaSpider(country="ch")


@pytest.fixture
def items(spider, payload):
    response = json_response(URL, payload, page=1)
    return [spider.parse_row(r, response) for r in spider.extract_rows(response)]


def test_source_declare_ses_prerequis():
    assert SOURCE.requires_env == ("ADZUNA_APP_ID", "ADZUNA_APP_KEY")
    assert SOURCE.access == "api"


def test_prerequis_manquants_sont_signales(monkeypatch):
    """Mieux vaut refuser de partir que collecter zero offre sans explication."""
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
    assert set(SOURCE.missing_env()) == {"ADZUNA_APP_ID", "ADZUNA_APP_KEY"}

    monkeypatch.setenv("ADZUNA_APP_ID", "x")
    monkeypatch.setenv("ADZUNA_APP_KEY", "y")
    assert SOURCE.missing_env() == ()


def test_offres_exploitables(items):
    assert len(items) == 3
    for item in items:
        assert_usable(item)
        assert item.country == "CH"


def test_offre_complete(items):
    item = items[0]
    assert item.title == "Développeur Python Senior"
    assert item.company == "ACME Technologies SA"
    assert item.city == "Genève"
    assert item.region == "Genève"
    assert item.lat == pytest.approx(46.2044)
    assert item.posted_at == "2026-08-19"
    assert item.contract_type == "permanent"
    assert item.occupations == ["it-jobs"]
    assert "Django" in item.description


def test_salaire_annonce_conserve(items):
    assert items[0].salary_min == 95000.0
    assert items[0].salary_max == 120000.0
    assert items[0].salary_currency == "CHF"


def test_salaire_estime_rejete(items):
    """Adzuna complete les offres muettes par une prediction de son modele.

    L'enregistrer dans le meme champ qu'un salaire publie presenterait une
    estimation comme un fait annonce par l'employeur.
    """
    estimee = items[1]
    assert estimee.salary_min is None
    assert estimee.salary_max is None
    assert estimee.salary_currency is None


def test_offre_minimale_acceptee(items):
    """Sans salaire ni coordonnees, une offre reste utile."""
    minimale = items[2]
    assert_usable(minimale)
    assert minimale.salary_min is None
    assert minimale.lat is None
    assert minimale.city == "Lausanne"
    assert minimale.region == "Vaud"


def test_devise_deduite_du_pays():
    """Adzuna renvoie des montants sans preciser la devise."""
    from jobs_scrape_mod_adzuna.spider import CURRENCIES

    assert CURRENCIES["ch"] == "CHF"
    assert CURRENCIES["fr"] == "EUR"


@pytest.mark.parametrize("row,attendu", [
    ({"contract_type": "permanent"}, "permanent"),
    ({"contract_type": "contract"}, "contractor"),
    ({"contract_time": "part_time"}, "part_time"),          # repli sur la duree
    ({"contract_type": "permanent", "contract_time": "part_time"}, "permanent"),
    ({}, None),
])
def test_contrat_combine_les_deux_notions(row, attendu):
    assert _contract(row) == attendu


def test_page_dans_le_chemin_pas_dans_les_parametres(spider, monkeypatch):
    """Adzuna numerote ses pages dans l'URL : /jobs/ch/search/3."""
    monkeypatch.setenv("ADZUNA_APP_ID", "id123")
    monkeypatch.setenv("ADZUNA_APP_KEY", "key456")
    spider = AdzunaSpider(country="ch", what="python")
    request = spider.build_request(3)
    assert "/jobs/ch/search/3?" in request.url
    assert "app_id=id123" in request.url
    assert "what=python" in request.url


def test_pagination_commence_a_un(spider):
    assert spider.start_page == 1


def test_pagination_s_arrete_sur_le_total(spider, payload):
    response = json_response(URL, payload)
    rows = spider.extract_rows(response)
    assert spider._total == 1284
    assert spider.has_next_page(response, rows, page=1) is True
    assert spider.has_next_page(response, rows, page=26) is False   # 26 x 50 >= 1284
    assert spider.has_next_page(response, [], page=1) is False


def test_cle_lue_dans_l_environnement(monkeypatch):
    monkeypatch.setenv("ADZUNA_APP_ID", "abc")
    monkeypatch.setenv("ADZUNA_APP_KEY", "def")
    spider = AdzunaSpider()
    assert spider.query_params(1)["app_id"] == "abc"
    assert spider.query_params(1)["app_key"] == "def"
