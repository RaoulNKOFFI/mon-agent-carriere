# 🤖 Mon Agent de Carrière — Dr Armel Raoul N'GUESSAN KOFFI

Agent personnel de recherche d'emploi (Data Analyst / Data Architect) :
recherche d'offres, scoring, lettres, fiches d'entretien et CV.

## 🚀 Utilisation
```bash
pip install -r requirements.txt
streamlit run interface_offres.py     # interface web (4 onglets)
python mon_agent.py                    # ligne de commande
```

## 🔑 Clés
Copiez config/cles_api.json.exemple en config/cles_api.json et mettez vos clés
Adzuna (gratuites sur developer.adzuna.com). En ligne : Secrets Streamlit.

## 📁 Structure
mon_agent.py · interface_offres.py · cv_generator.py · requirements.txt
config/ (mon_profil.json, offres_locales.csv, cles_api.json.exemple)

## 🔒 Ne publiez jamais config/cles_api.json (déjà exclu par .gitignore).
## ℹ️ Adzuna ne couvre pas la CI → vise le télétravail (France) + offres locales.
