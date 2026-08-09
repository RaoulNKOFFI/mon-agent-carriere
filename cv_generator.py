# -*- coding: utf-8 -*-
"""
====================================================================
 GÉNÉRATEUR DE CV — module de l'agent (compatible Streamlit Cloud)
====================================================================
Produit un CV Word (.docx) professionnel à partir de config/mon_profil.json.
Peut ADAPTER le CV à une offre précise : les compétences citées dans
l'annonce sont remontées en tête (CV « ciblé »).

Utilisation en Python :
    from cv_generator import generer_cv
    chemin = generer_cv(profil)                       # CV général
    chemin = generer_cv(profil, offre=uneOffre)       # CV ciblé sur l'offre
"""
import os, io, json, re, datetime as dt
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

NAVY = RGBColor(0x1F, 0x3B, 0x57)
ACCENT = RGBColor(0x2E, 0x75, 0xB6)
GREY = RGBColor(0x5B, 0x70, 0x80)
DARK = RGBColor(0x20, 0x30, 0x3F)


def _bord_bas(paragraph, color="2E75B6", size="6"):
    p = paragraph._p
    pPr = p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single"); bottom.set(qn("w:sz"), size)
    bottom.set(qn("w:space"), "4"); bottom.set(qn("w:color"), color)
    pbdr.append(bottom); pPr.append(pbdr)


def _titre_section(doc, texte):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(texte.upper())
    r.bold = True; r.font.size = Pt(12); r.font.color.rgb = NAVY
    r.font.name = "Calibri"
    _bord_bas(p)
    return p


def _competences_ordonnees(profil, offre=None):
    comps = list(profil["competences"])
    if offre:
        # remonter en tête les compétences citées dans l'offre
        txt = (offre.get("description", "") + " " +
               " ".join(offre.get("competences_requises", []))).lower()
        comps.sort(key=lambda c: 0 if c.lower() in txt else 1)
    return comps


def generer_cv(profil, offre=None, dossier=None, en_memoire=False):
    """Génère le CV. Retourne le chemin du fichier, ou des bytes si en_memoire=True."""
    cv = profil.get("cv", {})
    poste = (offre["titre"] if offre else profil["postes_vises"][0])
    comps = _competences_ordonnees(profil, offre)

    doc = Document()
    # marges
    for s in doc.sections:
        s.top_margin = Inches(0.7); s.bottom_margin = Inches(0.7)
        s.left_margin = Inches(0.8); s.right_margin = Inches(0.8)

    # --- En-tête ---
    p = doc.add_paragraph()
    r = p.add_run(profil["nom"]); r.bold = True; r.font.size = Pt(24)
    r.font.color.rgb = NAVY; r.font.name = "Calibri"
    p2 = doc.add_paragraph(); p2.paragraph_format.space_after = Pt(4)
    r2 = p2.add_run(poste); r2.bold = True; r2.font.size = Pt(13)
    r2.font.color.rgb = ACCENT; r2.font.name = "Calibri"
    p3 = doc.add_paragraph()
    r3 = p3.add_run(f"{profil['localisation']}  ·  {profil['telephone']}  ·  {profil['email']}")
    r3.font.size = Pt(9.5); r3.font.color.rgb = GREY; r3.font.name = "Calibri"

    # --- Profil pro ---
    _titre_section(doc, "Profil professionnel")
    if cv.get("resume_pro"):
        pr = doc.add_paragraph(); rr = pr.add_run(cv["resume_pro"])
        rr.font.size = Pt(10.5); rr.font.color.rgb = DARK; rr.font.name = "Calibri"

    # --- Compétences (tableau 3 colonnes) ---
    _titre_section(doc, "Compétences clés")
    n = len(comps); cols = 3; rows = (n + cols - 1) // cols
    t = doc.add_table(rows=rows, cols=cols)
    for i, c in enumerate(comps):
        cell = t.cell(i // cols, i % cols)
        cell.paragraphs[0].add_run("• " + c).font.size = Pt(9.5)
        cell.paragraphs[0].runs[0].font.name = "Calibri"
        cell.paragraphs[0].runs[0].font.color.rgb = NAVY

    # --- Expérience ---
    _titre_section(doc, "Expérience professionnelle")
    for e in cv.get("experiences", []):
        pe = doc.add_paragraph(); pe.paragraph_format.space_after = Pt(0)
        r = pe.add_run(e["poste"]); r.bold = True; r.font.size = Pt(11); r.font.color.rgb = NAVY
        r.font.name = "Calibri"
        r = pe.add_run("   " + e["entreprise"]); r.font.size = Pt(10.5); r.font.color.rgb = ACCENT
        r.font.name = "Calibri"
        pd = doc.add_paragraph(); pd.paragraph_format.space_after = Pt(2)
        r = pd.add_run(f"{e['periode']}" + (f"  ·  {e['lieu']}" if e.get("lieu") else ""))
        r.italic = True; r.font.size = Pt(9.5); r.font.color.rgb = GREY; r.font.name = "Calibri"
        for t_ in e.get("taches", []):
            pb = doc.add_paragraph(style="List Bullet"); pb.paragraph_format.space_after = Pt(2)
            rb = pb.add_run(t_); rb.font.size = Pt(10); rb.font.color.rgb = DARK; rb.font.name = "Calibri"

    # --- Formation ---
    _titre_section(doc, "Formation")
    for f in cv.get("formations", []):
        pf = doc.add_paragraph(style="List Bullet"); pf.paragraph_format.space_after = Pt(2)
        rf = pf.add_run(f["intitule"]); rf.font.size = Pt(10); rf.font.color.rgb = DARK; rf.font.name = "Calibri"
        if f.get("annee"):
            ra = pf.add_run(f"   ({f['annee']})"); ra.font.size = Pt(9.5); ra.font.color.rgb = GREY

    # --- Atouts & langues ---
    _titre_section(doc, "Atouts & langues")
    if cv.get("atouts"):
        for a in cv["atouts"]:
            pa = doc.add_paragraph(style="List Bullet"); pa.paragraph_format.space_after = Pt(2)
            ra = pa.add_run(a); ra.font.size = Pt(10); ra.font.color.rgb = DARK; ra.font.name = "Calibri"
    pl = doc.add_paragraph()
    rl = pl.add_run("Langues : " + " · ".join(profil.get("langues", [])))
    rl.font.size = Pt(10); rl.font.color.rgb = DARK; rl.font.name = "Calibri"

    if en_memoire:
        buf = io.BytesIO(); doc.save(buf); return buf.getvalue()

    dossier = dossier or os.path.join(os.path.dirname(os.path.abspath(__file__)), "sorties")
    os.makedirs(dossier, exist_ok=True)
    suffixe = ("_" + re.sub(r"[^A-Za-z0-9]", "_", offre["entreprise"])[:15]) if offre else ""
    chemin = os.path.join(dossier, f"CV_{re.sub(r'[^A-Za-z0-9]','_',profil['nom'])}{suffixe}.docx")
    doc.save(chemin)
    return chemin


if __name__ == "__main__":
    import json
    prof = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       "config", "mon_profil.json"), encoding="utf-8"))
    print("CV général :", generer_cv(prof))
