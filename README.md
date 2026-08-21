# jobs-scrape-mod-adzuna

Collecteur [jobs-scrape](https://github.com/XavierBeheydt/jobs-scrape) pour
**Adzuna**, agregateur d'offres couvrant la **France** et la **Suisse**.

## Pourquoi ce module existe

Il remplit le role que
[`jobs-scrape-mod-indeed`](https://github.com/XavierBeheydt/jobs-scrape-mod-indeed)
ne peut pas tenir : une couverture large et multi-employeurs, obtenue par un
**canal officiel** plutot qu'en contournant une protection.

L'API est documentee, et la cle d'application s'obtient gratuitement par simple
inscription -- **pas d'OAuth**, ce qui respecte la contrainte du projet.

## Configuration

```bash
export ADZUNA_APP_ID=votre_identifiant
export ADZUNA_APP_KEY=votre_cle
```

Inscription : <https://developer.adzuna.com/>

Sans ces variables, `jobs-scrape list` affiche le module comme incomplet et
`crawl` refuse de partir en le disant -- plutot que de rendre zero offre sans
explication.

## Les salaires estimes ne sont pas enregistres

Adzuna complete les annonces sans remuneration par une **estimation issue de son
propre modele**, signalee par `salary_is_predicted`. Ce module ne conserve que
les montants reellement publies par l'employeur.

Ranger une prediction dans le meme champ qu'un salaire annonce reviendrait a
presenter une estimation comme un fait -- et fausserait toute statistique
construite ensuite sur ces donnees.

## Deux notions de contrat

Adzuna expose `contract_type` (`permanent` / `contract`) **et** `contract_time`
(`full_time` / `part_time`). Le schema commun n'a qu'un champ : on privilegie la
nature du contrat, plus discriminante, avec repli sur la duree.

## Utilisation

```bash
uv run jobs-scrape crawl adzuna --limit 100
uv run jobs-scrape crawl adzuna -a country=fr -a what="data engineer"
uv run jobs-scrape crawl adzuna -a where=Genève -a distance=30 -a max_days_old=7
```

| Argument | Defaut | Role |
|---|---|---|
| `country` | `ch` | code pays (`ch`, `fr`, `de`, `it`…) |
| `what` | — | mots-cles |
| `where` | — | lieu de reference |
| `distance` | — | rayon autour de `where`, en kilometres |
| `max_days_old` | — | age maximal des annonces, en jours |
| `category` | — | etiquette de categorie Adzuna |

## Note sur les tests

La fixture est **synthetique** : elle reproduit fidelement le schema officiel
(`Adzuna::API::Response::Job`, releve sur `api.adzuna.com/v1/api-docs` le
2026-08-21) mais n'est pas une reponse enregistree, faute de cle d'API au moment
de l'ecriture. Elle couvre trois cas representatifs : offre complete, offre au
salaire estime, offre minimale.

**Le module n'a donc pas ete confronte a l'API reelle.** C'est le seul du projet
dans ce cas ; a verifier des qu'une cle est disponible.

## Developpement

```bash
uv venv
uv pip install git+https://github.com/XavierBeheydt/jobs-scrape.git
uv pip install -e ".[dev]"
uv run pytest -q
```
