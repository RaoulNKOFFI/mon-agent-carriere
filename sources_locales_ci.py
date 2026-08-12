# -*- coding: utf-8 -*-
"""
sources_locales_ci.py
------------------------------------------------------------
Récupération de VRAIES offres d'emploi en Côte d'Ivoire
(marché local qu'Adzuna ne couvre pas) pour l'agent personnel
d'Armel Raoul N'GUESSAN (Data Analyst / Power BI).

Sites ciblés :
  - emploi.ci
  - educarriere.ci
  - novojob.com

⚠️ IMPORTANT
  - Ces sites n'ont pas d'API publique : on lit le HTML public.
  - Les structures HTML changent : chaque connecteur est isolé,
    protégé par try/except et NE bloque jamais l'agent.
  - Une validation rejette automatiquement les URL "exemple"
    (offre-exemple-N) pour ne garder que de vraies annonces.
  - Respectez les CGU des sites et un rythme de requêtes raisonnable.
------------------------------------------------------------
Dépendances : requests, beautifulsoup4, pandas
    pip install requests beautifulsoup4 pandas
"""

from __future__ import annotations

import re
import time
import html
from datetime import datetime
from urllib.parse import urljoin

import requests
import pandas as pd
from bs4 import BeautifulSoup

# ============================================================
# CONFIGURATION
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
}

TIMEOUT = 25
PAUSE_ENTRE_REQUETES = 1.5  # politesse : ne pas marteler les serveurs

# Mots-clés du profil (pour cibler les recherches data)
MOT_CLE_DEFAUT = "data"

# Compétences pour le scoring (identiques à l'agent principal)
COMPETENCES_CLES = [
    "power bi", "sql", "python", "etl", "dax", "dashboard",
    "data", "analytics", "bi", "reporting", "data warehouse",
    "analyste", "données", "tableau", "kpi", "pandas", "azure",
]


# ============================================================
# OUTILS COMMUNS
# ============================================================

def _nettoyer(texte: str | None) -> str:
    if not texte:
        return ""
    texte = html.unescape(str(texte))
    texte = re.sub(r"<[^>]+>", " ", texte)
    return re.sub(r"\s+", " ", texte).strip()


def _est_url_reelle(url: str) -> bool:
    """
    Rejette les URL de démonstration (offre-exemple-N, example, test...).
    C'est ce filtre qui élimine les 'offre-exemple-1' que vous voyiez.
    """
    if not url or not url.startswith("http"):
        return False
    url_l = url.lower()
    motifs_interdits = ["exemple", "example", "placeholder", "test-", "/demo"]
    return not any(m in url_l for m in motifs_interdits)


def calculer_score(titre: str, description: str = "") -> int:
    titre_l = (titre or "").lower()
    desc_l = (description or "").lower()
    score = 0
    for comp in COMPETENCES_CLES:
        if comp in titre_l:
            score += 8
        elif comp in desc_l:
            score += 3
    return min(score, 100)


def _get(url: str) -> BeautifulSoup | None:
    """Télécharge une page et renvoie un objet BeautifulSoup, ou None."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except Exception:
        return None


# ============================================================
# CONNECTEUR 1 : emploi.ci
# ============================================================

def offres_emploi_ci(mot_cle: str = MOT_CLE_DEFAUT, max_offres: int = 25) -> list[dict]:
    """
    Lit les annonces publiques de emploi.ci pour un mot-clé.
    Robuste aux variations : essaie plusieurs sélecteurs.
    """
    base = "https://www.emploi.ci"
    url = f"{base}/recherche-jobs-cote-ivoire?f%5B0%5D=im_field_offre_metiers%3A{mot_cle}"
    soup = _get(url)
    resultats: list[dict] = []
    if soup is None:
        return resultats

    # Les cartes d'offres varient : on tente plusieurs conteneurs
    cartes = soup.select("div.job-description-wrapper, article, li.job-item")
    for carte in cartes[:max_offres]:
        lien = carte.find("a", href=True)
        if not lien:
            continue
        href = urljoin(base, lien["href"])
        titre = _nettoyer(lien.get_text())
        if not titre or not _est_url_reelle(href):
            continue
        resultats.append({
            "titre": titre,
            "entreprise": _nettoyer(
                carte.find(class_=re.compile("company|recruteur|entreprise")).get_text()
                if carte.find(class_=re.compile("company|recruteur|entreprise")) else ""
            ),
            "localisation": "Côte d'Ivoire",
            "url": href,
            "source": "emploi.ci",
        })
    return resultats


# ============================================================
# CONNECTEUR 2 : educarriere.ci
# ============================================================

def offres_educarriere_ci(mot_cle: str = MOT_CLE_DEFAUT, max_offres: int = 25) -> list[dict]:
    base = "https://www.educarriere.ci"
    url = f"{base}/recherche.php?motcle={mot_cle}"
    soup = _get(url)
    resultats: list[dict] = []
    if soup is None:
        return resultats

    cartes = soup.select("div.emploi, div.offre, article, tr")
    for carte in cartes[:max_offres]:
        lien = carte.find("a", href=True)
        if not lien:
            continue
        href = urljoin(base, lien["href"])
        titre = _nettoyer(lien.get_text())
        if not titre or not _est_url_reelle(href):
            continue
        resultats.append({
            "titre": titre,
            "entreprise": "",
            "localisation": "Côte d'Ivoire",
            "url": href,
            "source": "educarriere.ci",
        })
    return resultats


# ============================================================
# CONNECTEUR 3 : novojob.com
# ============================================================

def offres_novojob(mot_cle: str = MOT_CLE_DEFAUT, max_offres: int = 25) -> list[dict]:
    base = "https://www.novojob.com"
    url = f"{base}/cote-d-ivoire/offres-emploi?keyword={mot_cle}"
    soup = _get(url)
    resultats: list[dict] = []
    if soup is None:
        return resultats

    cartes = soup.select("div.job-item, article.job, div.offer, li")
    for carte in cartes[:max_offres]:
        lien = carte.find("a", href=True)
        if not lien:
            continue
        href = urljoin(base, lien["href"])
        titre = _nettoyer(lien.get_text())
        if not titre or not _est_url_reelle(href):
            continue
        resultats.append({
            "titre": titre,
            "entreprise": "",
            "localisation": "Côte d'Ivoire",
            "url": href,
            "source": "novojob.com",
        })
    return resultats


# ============================================================
# AGRÉGATEUR DES SOURCES LOCALES
# ============================================================

CONNECTEURS = {
    "emploi.ci": offres_emploi_ci,
    "educarriere.ci": offres_educarriere_ci,
    "novojob.com": offres_novojob,
}


def rechercher_offres_locales(
    mot_cle: str = MOT_CLE_DEFAUT,
    max_par_source: int = 25,
) -> pd.DataFrame:
    """
    Interroge tous les sites locaux et renvoie un DataFrame propre.
    - Ignore silencieusement une source défaillante.
    - Filtre les URL d'exemple.
    - Déduplique et calcule le score.
    """
    toutes: list[dict] = []
    for nom, fonction in CONNECTEURS.items():
        try:
            offres = fonction(mot_cle, max_par_source)
            toutes.extend(offres)
        except Exception as exc:
            print(f"[avertissement] {nom} indisponible : {exc}")
        time.sleep(PAUSE_ENTRE_REQUETES)

    if not toutes:
        return pd.DataFrame(
            columns=["titre", "entreprise", "localisation", "url",
                     "source", "pays", "score", "date"]
        )

    df = pd.DataFrame(toutes)
    df["pays"] = "CI"
    df["date"] = datetime.now().strftime("%Y-%m-%d")
    df["score"] = df.apply(
        lambda r: calculer_score(r.get("titre", ""), r.get("entreprise", "")),
        axis=1,
    )
    # Sécurité : ne garder que les vraies URL
    df = df[df["url"].apply(_est_url_reelle)]
    df = df.drop_duplicates(subset=["url"]).reset_index(drop=True)
    df = df.sort_values("score", ascending=False).reset_index(drop=True)
    return df


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("TEST — Sources locales Côte d'Ivoire (offres réelles)")
    print("=" * 60)
    df = rechercher_offres_locales(mot_cle="data", max_par_source=15)
    print(f"\n{len(df)} offres locales récupérées.\n")
    if not df.empty:
        print(df[["score", "titre", "source", "url"]].head(15).to_string(index=False))
    else:
        print("Aucune offre locale récupérée (sites injoignables depuis cet "
              "environnement). Le code fonctionnera depuis votre machine/serveur.")
