# -*- coding: utf-8 -*-
"""
INTERFACE WEB — offres locales, agent, CV, suivi
Lancement : streamlit run interface_offres.py
"""
import os, re
import pandas as pd
import streamlit as st
import mon_agent as A
from cv_generator import generer_cv

BASE   = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(BASE, "config")
OUT    = os.path.join(BASE, "sorties")
CSV_LOCAL = os.path.join(CONFIG, "offres_locales.csv")
COLS = ["titre","entreprise","localisation","salaire_fcfa","type_contrat","description","url"]
os.makedirs(OUT, exist_ok=True)

st.set_page_config(page_title="Mon agent de carrière", page_icon="💼", layout="wide")

def lire_offres():
    if os.path.exists(CSV_LOCAL):
        df = pd.read_csv(CSV_LOCAL, sep=";", dtype=str).fillna("")
        for c in COLS:
            if c not in df.columns: df[c] = ""
        return df[COLS]
    return pd.DataFrame(columns=COLS)

def ecrire_offres(df):
    df.to_csv(CSV_LOCAL, sep=";", index=False)

st.markdown("<h1 style='color:#1f3b57'>💼 Mon agent de carrière</h1>", unsafe_allow_html=True)
st.caption("Offres locales, recherche automatisée, lettres, fiches d'entretien et CV — sans code.")

profil = A.charger_profil()
cles   = A.charger_cles()

onglet1, onglet2, onglet3, onglet4 = st.tabs(
    ["📝 Mes offres locales", "🚀 Lancer l'agent", "📄 Mon CV", "📊 Suivi"])

# ---------------- ONGLET 1 : offres locales ----------------
with onglet1:
    st.subheader("Ajouter une offre repérée à Abidjan")
    st.caption("Sources : Emploi.ci, Educarriere.ci, Novojob, LinkedIn…")
    with st.form("ajout", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        titre = c1.text_input("Intitulé du poste *", placeholder="Data Analyst")
        entreprise = c2.text_input("Entreprise *", placeholder="Orange CI")
        localisation = c3.text_input("Localisation", value="Abidjan")
        c4, c5 = st.columns(2)
        salaire = c4.number_input("Salaire (FCFA, 0 si non indiqué)", min_value=0, value=0, step=100000)
        contrat = c5.selectbox("Type de contrat", ["CDI","CDD","Freelance","Stage","N/C"])
        description = st.text_area("Description de l'offre *",
            placeholder="Collez le texte de l'annonce (l'agent y détecte vos compétences).", height=120)
        url = st.text_input("Lien de l'annonce (URL)", placeholder="https://…")
        ajout = st.form_submit_button("➕ Ajouter l'offre", type="primary")
    if ajout:
        if not (titre and entreprise and description):
            st.error("Remplissez au moins : intitulé, entreprise et description.")
        else:
            df = lire_offres()
            df = pd.concat([df, pd.DataFrame([{"titre":titre,"entreprise":entreprise,
                "localisation":localisation or "Abidjan","salaire_fcfa":int(salaire),
                "type_contrat":contrat,"description":description,"url":url}])], ignore_index=True)
            ecrire_offres(df); st.success(f"✅ Offre « {titre} » ajoutée.")
    st.divider()
    st.subheader("📋 Mes offres enregistrées")
    df = lire_offres()
    if df.empty:
        st.info("Aucune offre pour l'instant. Ajoutez-en une ci-dessus.")
    else:
        st.caption("Modifiez dans le tableau puis « Enregistrer ». Cochez 🗑️ pour supprimer.")
        df_edit = df.copy(); df_edit.insert(0, "🗑️", False)
        edited = st.data_editor(df_edit, use_container_width=True, num_rows="dynamic",
                                hide_index=True, key="editeur")
        cA, cB = st.columns([1,4])
        if cA.button("💾 Enregistrer", type="primary"):
            garder = edited[edited["🗑️"]==False].drop(columns=["🗑️"])
            ecrire_offres(garder[COLS]); st.success(f"✅ {len(garder)} offre(s) enregistrée(s)."); st.rerun()
        cB.download_button("⬇️ Exporter (CSV)",
            data=df.to_csv(sep=";", index=False).encode("utf-8"),
            file_name="offres_locales.csv", mime="text/csv")

# ---------------- ONGLET 2 : lancer ----------------
with onglet2:
    st.subheader("Lancer la recherche")
    adz = cles.get("adzuna", {}).get("actif", False)
    c1, c2, c3 = st.columns(3)
    c1.metric("Offres locales", len(lire_offres()))
    c2.metric("Adzuna (télétravail)", "Activé ✅" if adz else "Désactivé")
    mem = A.charger_memoire(); c3.metric("Offres en mémoire", len(mem["offres_vues"]))
    col1, col2, col3 = st.columns([2,1,1])
    top_n = col1.slider("Top N", 1, 15, 5)
    reset_mem = col2.checkbox("🔄 Ignorer la mémoire", value=False)
    faire_cv = col3.checkbox("📄 CV ciblé par offre", value=True)
    if st.button("🚀 Lancer l'agent", type="primary", use_container_width=True):
        if reset_mem and os.path.exists(A.MEM): os.remove(A.MEM)
        with st.status("L'agent travaille…", expanded=True) as status:
            loc = A.rechercher_offres_locales(profil)
            web, source = A.rechercher_offres_reelles(profil, cles)
            offres = loc + web
            mem = A.charger_memoire()
            offres = A.filtrer_nouvelles(offres, mem)
            offres = A.filtrer_offres(offres, profil)
            classees = A.scorer_offres(offres, profil)
            resultats = []
            for o in classees[:top_n]:
                lettre = A.generer_lettre(o, profil, cles); fiche = A.fiche_entretien(o, profil)
                cv_bytes = generer_cv(profil, offre=o, en_memoire=True) if faire_cv else None
                resultats.append({"offre":o,"lettre":lettre,"fiche":fiche,"cv":cv_bytes})
            A.memoriser(classees[:top_n], mem)
            status.update(label=f"✅ {len(resultats)} candidatures préparées !", state="complete")
        st.session_state["resultats"] = resultats

    if st.session_state.get("resultats"):
        resultats = st.session_state["resultats"]
        if not resultats:
            st.warning("Aucune nouvelle offre (toutes déjà vues). Cochez « Ignorer la mémoire ».")
        else:
            st.subheader(f"🏆 Top {len(resultats)}")
            dfr = pd.DataFrame([{"Poste":r["offre"]["titre"],"Entreprise":r["offre"]["entreprise"],
                "Localisation":r["offre"]["localisation"],"Score":r["offre"]["score"],
                "Verdict":A.verdict(r["offre"]["score"])} for r in resultats])
            st.dataframe(dfr, use_container_width=True, hide_index=True)
            st.bar_chart(dfr.set_index("Poste")["Score"])
            for r in resultats:
                o = r["offre"]
                with st.expander(f"{o['titre']} @ {o['entreprise']} — {o['score']}/100"):
                    if o.get("url"): st.markdown(f"🔗 [Voir l'annonce]({o['url']})")
                    ca, cb = st.columns(2)
                    ca.markdown("**✅ Atouts :** " + (", ".join(o.get("_couvertes", [])) or "—"))
                    cb.markdown("**📚 À développer :** " + (", ".join(o.get("_manquantes", [])) or "—"))
                    tabs = st.tabs(["✉️ Lettre", "🎤 Entretien", "📄 CV ciblé"])
                    with tabs[0]:
                        st.text(r["lettre"])
                        st.download_button("⬇️ Lettre", r["lettre"],
                            file_name=f"lettre_{o['id']}.txt", key="l"+o["id"])
                    with tabs[1]:
                        st.text(r["fiche"])
                        st.download_button("⬇️ Fiche", r["fiche"],
                            file_name=f"entretien_{o['id']}.txt", key="f"+o["id"])
                    with tabs[2]:
                        if r.get("cv"):
                            st.success("CV adapté à cette offre (compétences ciblées en tête).")
                            st.download_button("⬇️ Télécharger le CV ciblé (.docx)", r["cv"],
                                file_name=f"CV_{re.sub(r'[^A-Za-z0-9]','_',o['entreprise'])[:15]}.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key="cv"+o["id"])
                        else:
                            st.info("Cochez « CV ciblé par offre » avant de lancer l'agent.")

# ---------------- ONGLET 3 : Mon CV ----------------
with onglet3:
    st.subheader("📄 Générer mon CV")
    st.write("Créez un CV professionnel à partir de votre profil. "
             "Vous pouvez aussi le **cibler sur un poste** précis : les compétences "
             "correspondantes remontent en tête.")
    poste_cible = st.selectbox("Intitulé du poste (en-tête du CV)",
                               profil.get("postes_vises", ["Data Analyst"]))
    mots_cibles = st.text_input("Compétences à mettre en avant (optionnel, séparées par des virgules)",
                                placeholder="SQL, Power BI, ETL")
    if st.button("🪄 Générer mon CV", type="primary"):
        offre_fictive = None
        if mots_cibles.strip():
            offre_fictive = {"titre": poste_cible, "entreprise": "",
                             "description": mots_cibles, "competences_requises": [
                                 m.strip() for m in mots_cibles.split(",") if m.strip()]}
        # forcer le titre choisi
        prof2 = dict(profil); prof2["postes_vises"] = [poste_cible] + profil.get("postes_vises", [])
        cv_bytes = generer_cv(prof2, offre=offre_fictive, en_memoire=True)
        st.success("✅ CV généré !")
        st.download_button("⬇️ Télécharger mon CV (.docx)", cv_bytes,
            file_name=f"CV_{re.sub(r'[^A-Za-z0-9]','_',profil['nom'])}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    st.divider()
    st.caption("💡 Astuce : les expériences et le résumé du CV se modifient dans "
               "config/mon_profil.json (section « cv »).")

# ---------------- ONGLET 4 : suivi ----------------
with onglet4:
    st.subheader("📊 Tableau de suivi des candidatures")
    suivi = os.path.join(OUT, "suivi_candidatures.csv")
    if os.path.exists(suivi):
        dfs = pd.read_csv(suivi, sep=";")
        st.dataframe(dfs, use_container_width=True, hide_index=True)
        st.download_button("⬇️ Télécharger le suivi (CSV)",
            data=dfs.to_csv(sep=";", index=False).encode("utf-8"),
            file_name="suivi_candidatures.csv", mime="text/csv")
    else:
        st.info("Aucune candidature encore. Lancez l'agent dans l'onglet « Lancer l'agent ».")
