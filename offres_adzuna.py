# -*- coding: utf-8 -*-
"""
offres_adzuna.py
------------------------------------------------------------
Module de récupération de VRAIES offres d'emploi pour l'agent
personnel d'Armel Raoul N'GUESSAN (Data Analyst / Power BI).

Remplace la lecture statique de data/offres_emploi.csv (démo)
par un appel réel à l'API Adzuna, avec :
  - repli automatique sur le CSV si l'API échoue (mode hors-ligne)
  - gestion des secrets (Streamlit secrets OU variables d'env.)
  - scoring d'adéquation orienté profil data
  - déduplication et nettoyage
------------------------------------------------------------
Dépendances : requests, pandas  (et streamlit en option)
    pip install requests pandas streamlit
"""

from __future__ import annotations

import os
import re
import html
from datetime import datetime
from pathlib import Path

import requests
import pandas as pd

# ============================================================
# 1. CONFIGURATION
# ============================================================

# Chemin du CSV de secours (votre ancien fichier de démo)
CSV_FALLBACK = Path("data/offres_emploi.csv")

# Pays couverts par Adzuna les plus pertinents pour vous
# (Adzuna NE couvre PAS la Côte d'Ivoire : voir sources locales)
PAYS_DEFAUT = "fr"          # France (télétravail + marché francophone)
PAYS_ALTERNATIFS = ["gb"]   # Royaume-Uni pour le remote international

# Mots-clés du profil (adaptés à votre CV Data Analyst / BI)
MOTS_CLES_DEFAUT = "data analyst"

# Mots-clés qui font monter le score d'adéquation (profil Armel)
COMPETENCES_CLES = [
    "power bi", "sql", "python", "etl", "dax", "dashboard",
    "data", "analytics", "bi", "reporting", "data warehouse",
    "tableau", "visualisation", "kpi", "pandas", "azure",
]


# ============================================================
# 2. GESTION DES SECRETS (clés API Adzuna)
# ============================================================

def _get_secret(nom: str, defaut: str | None = None) -> str | None:
    """
    Récupère une clé secrète depuis :
      1. les secrets Streamlit (st.secrets)  -> déploiement Streamlit Cloud
      2. les variables d'environnement       -> local / serveur
    """
    # a) Streamlit secrets (si l'app tourne sous Streamlit)
    try:
        import streamlit as st  # import local pour rester utilisable hors Streamlit
        if nom in st.secrets:
            return st.secrets[nom]
    except Exception:
        pass
    # b) Variables d'environnement
    return os.environ.get(nom, defaut)


def _identifiants_adzuna() -> tuple[str | None, str | None]:
    """Retourne (APP_ID, APP_KEY) ou (None, None) si absents."""
    app_id = _get_secret("ADZUNA_APP_ID")
    app_key = _get_secret("ADZUNA_APP_KEY")
    return app_id, app_key


# ============================================================
# 3. NETTOYAGE
# ============================================================

def _nettoyer_texte(texte: str | None) -> str:
    """Supprime les balises HTML et normalise les espaces."""
    if not texte:
        return ""
    texte = html.unescape(str(texte))
    texte = re.sub(r"<[^>]+>", " ", texte)      # retire les balises HTML
    texte = re.sub(r"\s+", " ", texte).strip()  # espaces multiples
    return texte


# ============================================================
# 4. SCORING D'ADÉQUATION (orienté profil data)
# ============================================================

def calculer_score(titre: str, description: str) -> int:
    """
    Score 0-100 basé sur la présence des compétences clés.
    Le titre pèse plus lourd que la description.
    """
    titre_l = (titre or "").lower()
    desc_l = (description or "").lower()

    score = 0
    for comp in COMPETENCES_CLES:
        if comp in titre_l:
            score += 8          # forte pondération dans le titre
        elif comp in desc_l:
            score += 3          # pondération dans la description

    return min(score, 100)      # plafonné à 100


# ============================================================
# 5. RÉCUPÉRATION DES OFFRES ADZUNA (le cœur de la correction)
# ============================================================

def recuperer_offres_adzuna(
    mots_cles: str = MOTS_CLES_DEFAUT,
    pays: str = PAYS_DEFAUT,
    lieu: str | None = None,
    nb_resultats: int = 50,
    remote_seulement: bool = False,
) -> pd.DataFrame:
    """
    Récupère de VRAIES offres depuis l'API Adzuna.

    Args:
        mots_cles : ex. "data analyst", "power bi"
        pays      : code Adzuna ("fr", "gb", ...)
        lieu      : ville / région (optionnel)
        nb_resultats : nombre d'offres à ramener (max 50 par page)
        remote_seulement : ne garder que le télétravail

    Returns:
        DataFrame normalisé (colonnes stables) ou DataFrame vide.
    Raises:
        RuntimeError si les identifiants sont absents.
        requests.HTTPError si l'API renvoie une erreur.
    """
    app_id, app_key = _identifiants_adzuna()
    if not app_id or not app_key:
        raise RuntimeError(
            "Identifiants Adzuna manquants. "
            "Définissez ADZUNA_APP_ID et ADZUNA_APP_KEY "
            "(secrets Streamlit ou variables d'environnement)."
        )

    url = f"https://api.adzuna.com/v1/api/jobs/{pays}/search/1"
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": min(nb_resultats, 50),
        "what": mots_cles,
        "content-type": "application/json",
        "sort_by": "date",           # les plus récentes d'abord
    }
    if lieu:
        params["where"] = lieu
    if remote_seulement:
        # Astuce simple : ajouter "remote" aux mots-clés
        params["what"] = f"{mots_cles} remote"

    reponse = requests.get(url, params=params, timeout=30)
    reponse.raise_for_status()
    data = reponse.json()

    lignes = []
    for job in data.get("results", []):
        titre = _nettoyer_texte(job.get("title"))
        description = _nettoyer_texte(job.get("description"))
        lignes.append({
            "id": job.get("id"),
            "titre": titre,
            "entreprise": (job.get("company") or {}).get("display_name", ""),
            "localisation": (job.get("location") or {}).get("display_name", ""),
            "pays": pays.upper(),
            "salaire_min": job.get("salary_min"),
            "salaire_max": job.get("salary_max"),
            "contrat": job.get("contract_time", ""),
            "description": description,
            "url": job.get("redirect_url", ""),
            "date": job.get("created", ""),
            "source": "Adzuna",
            "score": calculer_score(titre, description),
        })

    df = pd.DataFrame(lignes)
    if not df.empty:
        df = df.drop_duplicates(subset=["id"]).reset_index(drop=True)
        df = df.sort_values("score", ascending=False).reset_index(drop=True)
    return df


# ============================================================
# 6. REPLI CSV (mode démo / hors-ligne)
# ============================================================

def charger_csv_secours(chemin: Path = CSV_FALLBACK) -> pd.DataFrame:
    """Charge l'ancien CSV de démo si l'API n'est pas disponible."""
    if not chemin.exists():
        return pd.DataFrame()
    df = pd.read_csv(chemin)
    # On recalcule un score si les colonnes existent
    if {"titre", "description"}.issubset(df.columns):
        df["score"] = df.apply(
            lambda r: calculer_score(r.get("titre", ""), r.get("description", "")),
            axis=1,
        )
        df = df.sort_values("score", ascending=False).reset_index(drop=True)
    df["source"] = "CSV (démo)"
    return df


# ============================================================
# 7. POINT D'ENTRÉE UNIQUE POUR L'AGENT
# ============================================================

def rechercher_offres(
    mots_cles: str = MOTS_CLES_DEFAUT,
    pays: str = PAYS_DEFAUT,
    lieu: str | None = None,
    nb_resultats: int = 50,
    remote_seulement: bool = False,
    autoriser_repli: bool = True,
) -> tuple[pd.DataFrame, str]:
    """
    Fonction que l'agent doit appeler à la place de pd.read_csv(...).

    Tente Adzuna (vraies offres). En cas d'échec, bascule sur le CSV.

    Returns:
        (DataFrame, message_source)
    """
    try:
        df = recuperer_offres_adzuna(
            mots_cles=mots_cles,
            pays=pays,
            lieu=lieu,
            nb_resultats=nb_resultats,
            remote_seulement=remote_seulement,
        )
        if df.empty:
            raise ValueError("Aucune offre renvoyée par Adzuna.")
        return df, f"✅ {len(df)} vraies offres Adzuna ({pays.upper()})"
    except Exception as exc:
        if not autoriser_repli:
            raise
        df = charger_csv_secours()
        msg = (
            f"⚠️ Adzuna indisponible ({exc}). "
            f"Repli CSV : {len(df)} offres de démonstration."
        )
        return df, msg


# ============================================================
# 8. TEST EN LIGNE DE COMMANDE
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("TEST — Agent Data Analyst : récupération d'offres")
    print("Heure :", datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("=" * 60)

    offres, source = rechercher_offres(
        mots_cles="data analyst power bi",
        pays="fr",
        nb_resultats=20,
    )
    print("\nSource :", source, "\n")

    if offres.empty:
        print("Aucune offre disponible (API KO et pas de CSV de secours).")
    else:
        colonnes = [c for c in ["score", "titre", "entreprise",
                                "localisation", "source"] if c in offres.columns]
        print(offres[colonnes].head(10).to_string(index=False))
