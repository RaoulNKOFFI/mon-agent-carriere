# -*- coding: utf-8 -*-
"""
collecteur_offres.py
------------------------------------------------------------
Point d'entrée UNIQUE de l'agent : combine en une seule liste
  - les vraies offres internationales / remote (Adzuna)
  - les vraies offres locales Côte d'Ivoire (emploi.ci, etc.)
et élimine toute donnée d'exemple.

C'est CE fichier que votre agent (app.py) doit appeler.
------------------------------------------------------------
Dépendances : offres_adzuna.py, sources_locales_ci.py, pandas
"""

from __future__ import annotations

import pandas as pd

# Modules maison
try:
    from offres_adzuna import rechercher_offres as _adzuna
except Exception:
    _adzuna = None

try:
    from sources_locales_ci import rechercher_offres_locales as _locales
except Exception:
    _locales = None


COLONNES = [
    "score", "titre", "entreprise", "localisation",
    "pays", "url", "source", "date",
]


def _est_url_reelle(url) -> bool:
    """Filtre final anti-exemple, appliqué à TOUTES les sources."""
    if not isinstance(url, str) or not url.startswith("http"):
        return False
    url_l = url.lower()
    return not any(m in url_l for m in
                   ["exemple", "example", "placeholder", "test-", "/demo"])


def collecter_offres(
    mots_cles: str = "data analyst power bi",
    inclure_international: bool = True,
    inclure_local: bool = True,
    pays_international: str = "fr",
    max_resultats: int = 50,
) -> tuple[pd.DataFrame, list[str]]:
    """
    Rassemble toutes les offres réelles disponibles.

    Returns:
        (DataFrame trié par score, liste de messages d'état)
    """
    frames: list[pd.DataFrame] = []
    messages: list[str] = []

    # 1) International / remote via Adzuna
    if inclure_international and _adzuna is not None:
        try:
            df_int, msg = _adzuna(
                mots_cles=mots_cles,
                pays=pays_international,
                nb_resultats=max_resultats,
            )
            if not df_int.empty:
                frames.append(df_int)
            messages.append(f"International : {msg}")
        except Exception as exc:
            messages.append(f"International : ⚠️ échec ({exc})")
    elif inclure_international:
        messages.append("International : module Adzuna introuvable.")

    # 2) Local Côte d'Ivoire
    if inclure_local and _locales is not None:
        try:
            mot_local = mots_cles.split()[0]  # ex. "data"
            df_loc = _locales(mot_cle=mot_local)
            if not df_loc.empty:
                frames.append(df_loc)
            messages.append(f"Local CI : ✅ {len(df_loc)} offres réelles")
        except Exception as exc:
            messages.append(f"Local CI : ⚠️ échec ({exc})")
    elif inclure_local:
        messages.append("Local CI : module sources_locales_ci introuvable.")

    # 3) Fusion + nettoyage
    if not frames:
        return pd.DataFrame(columns=COLONNES), messages

    df = pd.concat(frames, ignore_index=True)

    # Harmoniser les colonnes manquantes
    for col in COLONNES:
        if col not in df.columns:
            df[col] = ""

    # Filtre anti-exemple GLOBAL (verrou final)
    df = df[df["url"].apply(_est_url_reelle)]

    # Déduplication et tri
    df = df.drop_duplicates(subset=["url"]).reset_index(drop=True)
    df = df.sort_values("score", ascending=False).reset_index(drop=True)

    messages.append(f"TOTAL après nettoyage : {len(df)} offres réelles")
    return df[COLONNES], messages


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("COLLECTEUR — Offres réelles (International + Local CI)")
    print("=" * 60)
    offres, etats = collecter_offres(mots_cles="data analyst power bi")
    print()
    for m in etats:
        print(" -", m)
    print()
    if offres.empty:
        print("Aucune offre réelle disponible dans cet environnement "
              "(réseau restreint). Fonctionnera depuis votre machine.")
    else:
        print(offres[["score", "titre", "source", "pays"]].head(15).to_string(index=False))
