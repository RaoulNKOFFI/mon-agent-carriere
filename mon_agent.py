# -*- coding: utf-8 -*-
"""
        MON AGENT DE CARRIÈRE  —  Dr Armel Raoul N'GUESSAN KOFFI
Sources de vraies offres : Careerjet (couvre la Côte d'Ivoire !) + Adzuna
(télétravail) + offres locales collées à la main. Scoring, lettres,
fiches d'entretien et CV. Clés : config/cles_api.json (local) ou st.secrets.
"""
import json, csv, os, re, sys, base64, datetime as dt

BASE   = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(BASE, "config")
OUT    = os.path.join(BASE, "sorties")
MEM    = os.path.join(BASE, "memoire.json")
os.makedirs(OUT, exist_ok=True)


def charger_profil():
    return json.load(open(os.path.join(CONFIG, "mon_profil.json"), encoding="utf-8"))

def charger_cles():
    chemin = os.path.join(CONFIG, "cles_api.json")
    if os.path.exists(chemin):
        return json.load(open(chemin, encoding="utf-8"))
    try:
        import streamlit as st
        cj  = st.secrets.get("careerjet", {})
        adz = st.secrets.get("adzuna", {})
        ant = st.secrets.get("anthropic", {})
        return {
            "careerjet": {"actif": bool(cj.get("api_key")),
                          "api_key": cj.get("api_key", ""),
                          "locale": cj.get("locale", "fr_CI")},
            "adzuna": {"actif": bool(adz.get("app_id")),
                       "app_id": adz.get("app_id", ""), "app_key": adz.get("app_key", "")},
            "anthropic": {"actif": bool(ant.get("actif", False)),
                          "cle": ant.get("cle", ""),
                          "modele": ant.get("modele", "claude-sonnet-4-6")},
            "email_recap": {"actif": False},
        }
    except Exception:
        return {"careerjet": {"actif": False}, "adzuna": {"actif": False},
                "anthropic": {"actif": False}, "email_recap": {"actif": False}}


# ================================================================== #
#  CAREERJET — couvre la Côte d'Ivoire (API v4)
# ================================================================== #
def rechercher_offres_careerjet(profil, cles):
    conf = cles.get("careerjet", {})
    if not conf.get("actif"):
        return []
    import urllib.request, urllib.parse
    rech = profil["recherche"]
    locale = conf.get("locale", "fr_CI")
    location = rech.get("localisation_locale", "Côte d'Ivoire")
    api_key = conf["api_key"]
    cred = base64.b64encode(f"{api_key}:".encode()).decode()
    headers = {
        "Authorization": f"Basic {cred}",
        "Content-Type": "application/json",
        "Referer": "https://armel-agent.streamlit.app/",
    }
    toutes = []
    for mot in rech["mots_cles_locaux"]:
        params = {
            "locale_code": locale,
            "keywords": mot,
            "location": location,
            "sort": "date",
            "page": 1,
            "page_size": rech.get("resultats_par_recherche", 20),
            "user_ip": "196.10.0.1",
            "user_agent": "MonAgentCarriere/1.0 (Streamlit)",
        }
        url = "https://search.api.careerjet.net/v4/query?" + urllib.parse.urlencode(params)
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.load(r)
            if data.get("type") != "JOBS":
                continue
            for j in data.get("jobs", []):
                import hashlib
                cle_unique = (j.get("url", "") or (j.get("title","")+j.get("company","")))
                ident = "CJ_" + hashlib.md5(cle_unique.encode()).hexdigest()[:16]
                toutes.append({
                    "id": ident,
                    "titre": (j.get("title") or "").strip(),
                    "entreprise": (j.get("company") or "N/C").strip(),
                    "localisation": (j.get("locations") or "Côte d'Ivoire").strip(),
                    "salaire_fcfa": 0,
                    "type_contrat": "N/C",
                    "competences_requises": _extraire_competences(j.get("description",""), profil),
                    "description": (j.get("description") or "")[:300],
                    "url": j.get("url", ""),
                })
        except Exception as e:
            print(f"⚠️  Careerjet — erreur pour « {mot} » : {e}")
    vus, uniques = set(), []
    for o in toutes:
        if o["id"] not in vus: vus.add(o["id"]); uniques.append(o)
    if uniques:
        print(f"🇨🇮 {len(uniques)} offres Careerjet (Côte d'Ivoire).\n")
    return uniques


# ================================================================== #
#  ADZUNA — télétravail (optionnel)
# ================================================================== #
def rechercher_offres_adzuna(profil, cles):
    conf = cles.get("adzuna", {})
    if not conf.get("actif"):
        return []
    import urllib.request, urllib.parse
    rech = profil["recherche"]; pays = rech.get("pays_code", "fr")
    toutes = []
    for mot in rech.get("mots_cles_remote", []):
        params = {"app_id": conf["app_id"], "app_key": conf["app_key"],
                  "what": mot, "where": rech.get("localisation_remote", "France"),
                  "results_per_page": rech.get("resultats_par_recherche", 20),
                  "content-type": "application/json"}
        url = f"https://api.adzuna.com/v1/api/jobs/{pays}/search/1?" + urllib.parse.urlencode(params)
        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                data = json.load(r)
            for j in data.get("results", []):
                toutes.append({
                    "id": "ADZ_"+str(j.get("id")), "titre": (j.get("title") or "").strip(),
                    "entreprise": (j.get("company", {}) or {}).get("display_name", "N/C"),
                    "localisation": (j.get("location", {}) or {}).get("display_name", "N/C"),
                    "salaire_fcfa": int(j.get("salary_min") or 0),
                    "type_contrat": j.get("contract_time", "N/C"),
                    "competences_requises": _extraire_competences(j.get("description",""), profil),
                    "description": (j.get("description") or "")[:300],
                    "url": j.get("redirect_url", "")})
        except Exception as e:
            print(f"⚠️  Adzuna — erreur pour « {mot} » : {e}")
    return toutes


def _extraire_competences(description, profil):
    desc = (description or "").lower()
    return [c for c in profil["competences"] if c.lower() in desc] or ["(voir description)"]

def _offres_demo():
    return [
        {"id":"D001","titre":"Data Analyst","entreprise":"Orange CI","localisation":"Abidjan",
         "salaire_fcfa":1200000,"type_contrat":"CDI",
         "competences_requises":["SQL","Power BI","Python","Excel avancé"],
         "description":"Analyser les données clients et produire des tableaux de bord.","url":""},
        {"id":"D002","titre":"Data Architect","entreprise":"MTN CI","localisation":"Abidjan",
         "salaire_fcfa":1800000,"type_contrat":"CDI",
         "competences_requises":["SQL","ETL","Modélisation dimensionnelle","Python","Data profiling"],
         "description":"Concevoir et maintenir l'entrepôt de données.","url":""},
    ]


def rechercher_offres_locales(profil):
    chemin = os.path.join(CONFIG, "offres_locales.csv")
    if not os.path.exists(chemin): return []
    offres = []
    with open(chemin, encoding="utf-8") as f:
        for ligne in csv.DictReader(f, delimiter=";"):
            titre = (ligne.get("titre") or "").strip()
            if not titre: continue
            desc = (ligne.get("description") or "").strip()
            try: sal = int(ligne.get("salaire_fcfa") or 0)
            except ValueError: sal = 0
            ident = "LOC_" + re.sub(r"[^a-z0-9]", "",
                        (titre + (ligne.get("entreprise") or "")).lower())[:24]
            offres.append({
                "id": ident, "titre": titre,
                "entreprise": (ligne.get("entreprise") or "N/C").strip(),
                "localisation": (ligne.get("localisation") or "Abidjan").strip(),
                "salaire_fcfa": sal, "type_contrat": (ligne.get("type_contrat") or "N/C").strip(),
                "competences_requises": _extraire_competences(desc, profil),
                "description": desc[:300], "url": (ligne.get("url") or "").strip()})
    if offres:
        print(f"🏠 {len(offres)} offres locales chargées.\n")
    return offres


def rechercher_toutes_offres(profil, cles):
    """Agrège toutes les sources : locales + Careerjet + Adzuna (+ démo si rien)."""
    sources = []
    off = rechercher_offres_locales(profil)
    if off: sources.append(("locale", off))
    cj = rechercher_offres_careerjet(profil, cles)
    if cj: sources.append(("careerjet", cj))
    adz = rechercher_offres_adzuna(profil, cles)
    if adz:
        print(f"🌐 {len(adz)} offres Adzuna (télétravail).\n"); sources.append(("adzuna", adz))
    if not sources:
        print("ℹ️  Aucune API active → MODE DÉMO.\n")
        return _offres_demo(), "demo"
    toutes, noms = [], []
    for nom, lst in sources:
        toutes += lst; noms.append(nom)
    return toutes, "+".join(noms)


# ================================================================== #
#  Mémoire · Filtrage · Scoring
# ================================================================== #
def charger_memoire():
    return json.load(open(MEM, encoding="utf-8")) if os.path.exists(MEM) \
           else {"offres_vues": [], "historique": []}

def sauver_memoire(m):
    json.dump(m, open(MEM, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def filtrer_nouvelles(offres, mem):
    vues = set(mem["offres_vues"]); return [o for o in offres if o["id"] not in vues]

def memoriser(offres, mem):
    for o in offres:
        if o["id"] not in mem["offres_vues"]:
            mem["offres_vues"].append(o["id"])
            mem["historique"].append({"id":o["id"],"titre":o["titre"],
                "entreprise":o["entreprise"],"score":o.get("score"),
                "date":dt.date.today().isoformat()})
    sauver_memoire(mem)

def _norm(c): return re.sub(r"[^a-z0-9]", "", c.lower())

def filtrer_offres(offres, profil):
    seuil = profil["preferences"]["salaire_min_fcfa"]
    return [o for o in offres if o["salaire_fcfa"] == 0 or o["salaire_fcfa"] >= seuil]

def scorer_offres(offres, profil):
    mes = {_norm(c) for c in profil["competences"]}
    postes = [p.lower() for p in profil["postes_vises"]]
    for o in offres:
        req = [_norm(c) for c in o["competences_requises"] if c != "(voir description)"]
        s_comp = (len([c for c in req if c in mes])/len(req)) if req else 0.4
        titre = o["titre"].lower()
        s_titre = 1.0 if any(p in titre or titre in p for p in postes) else \
                  (0.5 if any(m in titre for m in ["data","analyst","bi","formateur","données","analytics"]) else 0.0)
        dom = 1.0 if any(d.lower() in (o["titre"]+o["description"]).lower()
                         for d in profil["preferences"]["domaines_preferes"]) else 0.3
        o["score"] = round(min(60*s_comp + 20*s_titre + 20*dom, 100), 1)
        o["_couvertes"]  = [c for c in o["competences_requises"] if _norm(c) in mes]
        o["_manquantes"] = [c for c in o["competences_requises"]
                            if _norm(c) not in mes and c != "(voir description)"]
    return sorted(offres, key=lambda x: x["score"], reverse=True)

def verdict(s):
    return ("Excellent match" if s>=75 else "Bon match" if s>=55 else
            "Match moyen" if s>=40 else "Match faible")


def generer_lettre(offre, profil, cles):
    conf = cles.get("anthropic", {})
    if conf.get("actif"):
        try: return _lettre_llm(offre, profil, conf)
        except Exception as e: print(f"⚠️  IA indisponible ({e}) → gabarit.")
    return _lettre_gabarit(offre, profil)

def _lettre_gabarit(offre, profil):
    atouts = ", ".join(offre.get("_couvertes", [])[:5]) or "mon profil polyvalent"
    d = dt.date.today().strftime("%d/%m/%Y")
    return f"""{profil['nom']}
{profil['email']} · {profil['telephone']}
{profil['localisation']}
{d}

Objet : Candidature au poste de {offre['titre']} — {offre['entreprise']}

Madame, Monsieur,

Actuellement {profil['titre_actuel']}, je souhaite mettre mes compétences au
service de {offre['entreprise']} pour le poste de {offre['titre']}.

Je maîtrise en particulier {atouts}, compétences développées au fil de
{profil['annees_experience']} années d'expérience et de nombreux projets data.

Ce poste correspond précisément à mon projet professionnel : {profil['objectif']}

Je serais ravi d'échanger avec vous lors d'un entretien.

Veuillez agréer, Madame, Monsieur, l'expression de mes salutations distinguées.

{profil['nom']}
"""

def _lettre_llm(offre, profil, conf):
    import anthropic
    client = anthropic.Anthropic(api_key=conf["cle"])
    prompt = (f"Rédige une lettre de motivation en français (200 mots max, sobre).\n"
              f"Candidat : {profil['nom']}, {profil['titre_actuel']}, "
              f"{profil['annees_experience']} ans. Objectif : {profil['objectif']}\n"
              f"Poste : {offre['titre']} chez {offre['entreprise']}. "
              f"Description : {offre['description']}\n"
              f"Atouts : {', '.join(offre.get('_couvertes', []))}.")
    msg = client.messages.create(model=conf.get("modele","claude-sonnet-4-6"),
        max_tokens=700, messages=[{"role":"user","content":prompt}])
    entete = (f"{profil['nom']}\n{profil['email']} · {profil['telephone']}\n"
              f"{profil['localisation']}\n{dt.date.today().strftime('%d/%m/%Y')}\n\n")
    return entete + msg.content[0].text

def fiche_entretien(offre, profil):
    L = [f"FICHE ENTRETIEN — {offre['titre']} @ {offre['entreprise']}",
         f"Score : {offre['score']}/100 ({verdict(offre['score'])})",
         "="*60, "", "QUESTIONS PROBABLES :",
         f"• Pourquoi ce poste chez {offre['entreprise']} ?"]
    for c in offre.get("_couvertes", [])[:3]:
        L.append(f"• Un projet concret avec « {c} » ? (exemple chiffré)")
    for c in offre.get("_manquantes", [])[:2]:
        L.append(f"• Votre niveau sur « {c} » ? (capacité d'apprentissage)")
    L += ["• Une difficulté surmontée en projet ? (méthode STAR)", "",
          "QUESTIONS À POSER :",
          "• Comment mesure-t-on la réussite du poste à 6 mois ?",
          "• Quels sont les défis actuels de l'équipe ?",
          "• Perspectives d'évolution et de formation ?"]
    if offre.get("url"): L += ["", f"🔗 Offre : {offre['url']}"]
    return "\n".join(L)


def lancer(top_n=5):
    print("="*64); print(" MON AGENT DE CARRIÈRE — démarrage"); print("="*64)
    profil, cles, mem = charger_profil(), charger_cles(), charger_memoire()
    offres, source = rechercher_toutes_offres(profil, cles)
    avant = len(offres)
    offres = filtrer_nouvelles(offres, mem)
    print(f"🧠 {len(offres)} nouvelles ({avant-len(offres)} déjà vues ignorées).")
    offres = filtrer_offres(offres, profil)
    classees = scorer_offres(offres, profil)

    lignes, resultats = [], []
    for i, o in enumerate(classees[:top_n], 1):
        lettre = generer_lettre(o, profil, cles); fiche = fiche_entretien(o, profil)
        base = f"{o['id']}_{re.sub(r'[^A-Za-z0-9]','_',o['entreprise'])[:20]}"
        open(os.path.join(OUT, f"lettre_{base}.txt"),"w",encoding="utf-8").write(lettre)
        open(os.path.join(OUT, f"entretien_{base}.txt"),"w",encoding="utf-8").write(fiche)
        v = verdict(o["score"])
        print(f"  #{i} {o['titre']} @ {o['entreprise']} → {o['score']}/100 ({v})")
        lignes.append([dt.date.today().isoformat(), o["titre"], o["entreprise"],
                       o["localisation"], o["score"], v, "À postuler",
                       o.get("url",""), f"lettre_{base}.txt"])
        resultats.append({"offre": o, "verdict": v})

    suivi = os.path.join(OUT, "suivi_candidatures.csv"); existe = os.path.exists(suivi)
    with open(suivi, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        if not existe:
            w.writerow(["Date","Poste","Entreprise","Localisation","Score",
                        "Verdict","Statut","URL","Lettre"])
        w.writerows(lignes)
    memoriser(classees[:top_n], mem)
    print("="*64)
    print(f" ✅ {len(resultats)} candidatures dans « sorties/ » (sources : {source.upper()})")
    print("="*64)
    return resultats


if __name__ == "__main__":
    top = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    lancer(top_n=top)
