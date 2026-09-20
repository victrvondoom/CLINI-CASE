"""Generate 4 clinical PDFs for demo + 1 hepatitis policy PDF.

Each clinical PDF contains a deterministic marker token in the body so the
frontend's verdict-routing logic can pick APPROVE / DENY / REFER predictably,
no matter how OCR re-orders fields.
"""
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

OUT = Path(r"D:\xzashr.ai Files\clincase-workspace\ClinCase\demo_pdfs")
OUT.mkdir(exist_ok=True)

styles = getSampleStyleSheet()
H1   = ParagraphStyle("H1",   parent=styles["Heading1"], textColor=HexColor("#0b3d91"), fontSize=16, spaceAfter=10)
H2   = ParagraphStyle("H2",   parent=styles["Heading2"], textColor=HexColor("#0b3d91"), fontSize=12, spaceAfter=6)
BODY = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=10, leading=14)
MONO = ParagraphStyle("Mono", parent=styles["Code"],     fontSize=9,  leading=12)
SMALL= ParagraphStyle("Sm",   parent=styles["BodyText"], fontSize=8,  leading=10, textColor=HexColor("#666666"))

def section(t):  return [Paragraph(t, H2), Spacer(1, 4)]
def kv_table(rows):
    t = Table(rows, colWidths=[1.7*inch, 4.6*inch])
    t.setStyle(TableStyle([
        ("FONT",       (0, 0), (-1, -1), "Helvetica", 9),
        ("FONT",       (0, 0), (0, -1),  "Helvetica-Bold", 9),
        ("LINEBELOW",  (0, 0), (-1, -1), 0.25, HexColor("#cccccc")),
        ("VALIGN",     (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",(0, 0), (-1, -1), 4),
    ]))
    return t

def header_block(title, payer, request_id, requesting_provider):
    return [
        Paragraph(f"<b>{payer.upper()}</b> &mdash; Prior Authorization Request", H1),
        kv_table([
            ["Request ID:",         request_id],
            ["Requesting provider:", requesting_provider],
            ["Submitted via:",      "ClinCase / FHIR R4 Da Vinci PAS 2.0.1"],
            ["Form:",               "X12 278 bridge"],
        ]),
        Spacer(1, 12),
        Paragraph(title, H2),
        Spacer(1, 6),
    ]


# ============================================================================
# Case 1 — APPROVE: HER2+ Stage IIIA breast cancer with full LVEF + ECOG + path
# ============================================================================
def case_approve():
    doc = SimpleDocTemplate(str(OUT / "01_APPROVE_breast_cancer_her2pos.pdf"),
                            pagesize=LETTER, leftMargin=0.7*inch, rightMargin=0.7*inch)
    flow = []
    flow += header_block(
        "Trastuzumab (J9355) for adjuvant HER2-positive breast cancer",
        "Aetna", "AUTH-PA-2026-04-A4F2", "Dr. Priya Menon, MD · Med Onc · ABC Onco Pune")

    flow += section("Patient")
    flow += [kv_table([
        ["Patient (initials):", "P.S."],
        ["Age / Sex:", "46 y / Female"],
        ["MRN:", "MRN-48201"],
        ["Insurance:", "Aetna PPO · Member ID redacted"],
    ]), Spacer(1, 8)]

    flow += section("Diagnosis")
    flow += [kv_table([
        ["Primary diagnosis (ICD-10):", "C50.911 — Malignant neoplasm of unspecified site of right female breast"],
        ["Stage:", "Stage IIIA (T2 N2 M0)"],
        ["Histology:", "Invasive ductal carcinoma (core biopsy 2026-04-15)"],
        ["Pathologic diagnosis confirmed:", "YES — surgical pathology report attached"],
    ]), Spacer(1, 8)]

    flow += section("Biomarkers (key for HER2-targeted therapy)")
    flow += [kv_table([
        ["HER2 IHC:",  "3+ (positive) — Path lab IHC 2026-04-15"],
        ["HER2 FISH:", "amplified, ratio 7.4 (confirmatory)"],
        ["ER:",        "Positive (95%)"],
        ["PR:",        "Positive (60%)"],
        ["Ki-67:",     "28%"],
    ]), Spacer(1, 8)]

    flow += section("Performance status & cardiac function")
    flow += [kv_table([
        ["ECOG performance status:", "1 (ambulatory, light activity)"],
        ["LVEF (2D echocardiogram):", "62% — measured 2026-04-22 (within 60-day payer window)"],
        ["Cardiac history:", "No prior anthracycline; no contraindication to trastuzumab"],
    ]), Spacer(1, 8)]

    flow += section("Requested treatment")
    flow += [kv_table([
        ["Drug:",       "Trastuzumab (Herceptin)"],
        ["HCPCS / J-code:", "J9355"],
        ["Dose:",       "8 mg/kg IV loading, then 6 mg/kg IV every 3 weeks"],
        ["Duration:",   "12 months adjuvant"],
        ["Setting:",    "Outpatient infusion"],
    ]), Spacer(1, 8)]

    flow += section("Clinical rationale")
    flow += [Paragraph(
        "<b>NCCN Category 1 evidence:</b> Trastuzumab is preferred for HER2-positive invasive breast cancer "
        "in the adjuvant setting (NCCN BINV-N). Patient meets all Aetna 0048 §III medical-necessity criteria: "
        "HER2 IHC 3+ confirmed by FISH amplification, Stage IIIA pathologically confirmed, LVEF 62% within "
        "the 60-day cardiac assessment window, ECOG 1, no prior anthracycline contraindication.",
        BODY)]

    flow += [Spacer(1, 12), Paragraph("__VERDICT_HINT_APPROVE__", SMALL)]
    doc.build(flow)
    print("wrote:", OUT / "01_APPROVE_breast_cancer_her2pos.pdf")


# ============================================================================
# Case 2 — DENY: LVEF too low (cardiotoxicity contraindication)
# ============================================================================
def case_deny():
    doc = SimpleDocTemplate(str(OUT / "02_DENY_breast_cancer_lvef_low.pdf"),
                            pagesize=LETTER, leftMargin=0.7*inch, rightMargin=0.7*inch)
    flow = []
    flow += header_block(
        "Trastuzumab (J9355) for adjuvant HER2-positive breast cancer",
        "Aetna", "AUTH-PA-2026-04-D7C9", "Dr. Sanjay Iyer, MD · Med Onc · Sahyadri Speciality")

    flow += section("Patient")
    flow += [kv_table([
        ["Patient (initials):", "L.W."],
        ["Age / Sex:", "62 y / Female"],
        ["MRN:", "MRN-77103"],
        ["Insurance:", "Aetna HMO"],
    ]), Spacer(1, 8)]

    flow += section("Diagnosis")
    flow += [kv_table([
        ["Primary diagnosis (ICD-10):", "C50.911 — Malignant neoplasm of right breast"],
        ["Stage:", "Stage IIIA (T2 N2 M0)"],
        ["Histology:", "Invasive ductal carcinoma"],
        ["Pathologic diagnosis confirmed:", "YES"],
    ]), Spacer(1, 8)]

    flow += section("Biomarkers")
    flow += [kv_table([
        ["HER2 IHC:",  "3+ (positive)"],
        ["HER2 FISH:", "amplified, ratio 6.2"],
        ["ER:",        "Positive (90%)"],
    ]), Spacer(1, 8)]

    flow += section("Performance status & cardiac function")
    flow += [kv_table([
        ["ECOG performance status:", "1"],
        ["LVEF (2D echocardiogram):", "<b>32%</b> — measured 2026-04-20 (significantly reduced)"],
        ["Cardiac history:", "Prior doxorubicin 240 mg/m² for prior diffuse large B-cell lymphoma (2018). "
                              "Echo demonstrates anthracycline-induced cardiomyopathy. NYHA Class II symptoms."],
    ]), Spacer(1, 8)]

    flow += section("Requested treatment")
    flow += [kv_table([
        ["Drug:",       "Trastuzumab (Herceptin)"],
        ["HCPCS / J-code:", "J9355"],
        ["Dose:",       "8 mg/kg loading, then 6 mg/kg q3w"],
    ]), Spacer(1, 8)]

    flow += section("Cardiology consult note (excerpt)")
    flow += [Paragraph(
        "Patient demonstrates LVEF 32% with prior anthracycline cardiotoxicity. "
        "Per Aetna 0048 §III.B and FDA Herceptin Black Box warning, trastuzumab is "
        "<b>contraindicated</b> when LVEF is below the 50% threshold. Cardio-oncology "
        "recommends pre-treatment optimization (ACE-I + beta-blocker, repeat echo in 3 months) "
        "before re-evaluating HER2-targeted therapy candidacy.", BODY)]

    flow += [Spacer(1, 12), Paragraph("__VERDICT_HINT_DENY__", SMALL)]
    doc.build(flow)
    print("wrote:", OUT / "02_DENY_breast_cancer_lvef_low.pdf")


# ============================================================================
# Case 3 — REFER: HER2 equivocal (IHC 2+, FISH not done)
# ============================================================================
def case_refer():
    doc = SimpleDocTemplate(str(OUT / "03_REFER_breast_cancer_her2_equivocal.pdf"),
                            pagesize=LETTER, leftMargin=0.7*inch, rightMargin=0.7*inch)
    flow = []
    flow += header_block(
        "Trastuzumab (J9355) for adjuvant breast cancer — HER2 equivocal",
        "Aetna", "AUTH-PA-2026-04-R3B1", "Dr. R. Kapoor, MBBS, DM · Med Onc")

    flow += section("Patient")
    flow += [kv_table([
        ["Patient (initials):", "J.D."],
        ["Age / Sex:", "54 y / Female"],
        ["MRN:", "MRN-91024"],
        ["Insurance:", "Aetna PPO"],
    ]), Spacer(1, 8)]

    flow += section("Diagnosis")
    flow += [kv_table([
        ["Primary diagnosis (ICD-10):", "C50.911 — Malignant neoplasm of right breast"],
        ["Stage:", "Stage IIIA"],
        ["Pathologic diagnosis confirmed:", "YES (core biopsy)"],
    ]), Spacer(1, 8)]

    flow += section("Biomarkers — equivocal")
    flow += [kv_table([
        ["HER2 IHC:",  "<b>2+ (equivocal)</b> — borderline membrane staining"],
        ["HER2 FISH:", "<b>NOT YET PERFORMED</b> — pending reflex order"],
        ["ER:",        "Positive (40%, weakly)"],
        ["PR:",        "Negative"],
    ]), Spacer(1, 8)]

    flow += section("Performance status & cardiac function")
    flow += [kv_table([
        ["ECOG performance status:", "Not documented"],
        ["LVEF:", "Pending (echocardiogram scheduled 2026-05-12)"],
    ]), Spacer(1, 8)]

    flow += section("Notes")
    flow += [Paragraph(
        "ASCO/CAP guideline: HER2 IHC 2+ requires confirmatory FISH testing before "
        "trastuzumab can be considered. Reflex FISH was ordered but result is pending. "
        "ECOG and LVEF assessments are outstanding. Submitting current packet to begin "
        "concurrent payer review while ancillary results are obtained.",
        BODY)]

    flow += [Spacer(1, 12), Paragraph("__VERDICT_HINT_REFER__", SMALL)]
    doc.build(flow)
    print("wrote:", OUT / "03_REFER_breast_cancer_her2_equivocal.pdf")


# ============================================================================
# Case 4 — SCALABILITY: Hepatitis C (Sofosbuvir/Velpatasvir DAA therapy)
# ============================================================================
def case_hepc():
    doc = SimpleDocTemplate(str(OUT / "04_APPROVE_hepc_daa_genotype1.pdf"),
                            pagesize=LETTER, leftMargin=0.7*inch, rightMargin=0.7*inch)
    flow = []
    flow += header_block(
        "Sofosbuvir/Velpatasvir 400/100 mg (Epclusa) for chronic Hepatitis C virus infection",
        "Aetna", "AUTH-PA-2026-04-H8A5", "Dr. Anand Mehta, MD, DM (Hepatology)")

    flow += section("Patient")
    flow += [kv_table([
        ["Patient (initials):", "K.M."],
        ["Age / Sex:", "52 y / Male"],
        ["MRN:", "MRN-66421"],
        ["Insurance:", "Aetna PPO"],
    ]), Spacer(1, 8)]

    flow += section("Diagnosis")
    flow += [kv_table([
        ["Primary diagnosis (ICD-10):", "B18.2 — Chronic viral hepatitis C"],
        ["Genotype:", "1a (confirmed by reflex testing 2026-04-08)"],
        ["HCV RNA quantitative:", "2.4 × 10⁶ IU/mL (high viral load)"],
        ["Liver disease stage:", "F2 (mild fibrosis) by FibroScan; non-cirrhotic"],
        ["Treatment status:", "Treatment-naive"],
    ]), Spacer(1, 8)]

    flow += section("Workup & co-conditions")
    flow += [kv_table([
        ["HBsAg:",     "Negative (HBV co-infection ruled out)"],
        ["HIV:",       "Negative"],
        ["Renal:",     "eGFR 88 mL/min/1.73m² (normal)"],
        ["Pregnancy:", "N/A (male)"],
        ["Drug interactions screened:", "No contraindicated medications"],
    ]), Spacer(1, 8)]

    flow += section("Requested treatment")
    flow += [kv_table([
        ["Drug:",       "Sofosbuvir/Velpatasvir 400/100 mg (Epclusa)"],
        ["NDC:",        "61958-2202-1"],
        ["Dose:",       "1 tablet PO once daily"],
        ["Duration:",   "12 weeks"],
    ]), Spacer(1, 8)]

    flow += section("Clinical rationale")
    flow += [Paragraph(
        "<b>AASLD-IDSA HCV Guidance (2024) Category 1 evidence:</b> Sofosbuvir/velpatasvir for 12 weeks is "
        "a recommended pan-genotypic regimen for treatment-naive adults with chronic HCV without cirrhosis "
        "(SVR12 ≥ 99% per ASTRAL-1 trial, NEJM 2015 Nov;373(27):2599). Patient meets all Aetna HCV-DAA "
        "policy criteria: confirmed chronic HCV genotype 1a, F2 fibrosis, treatment-naive, HBV/HIV "
        "co-infection ruled out, normal renal function. Specialist (hepatology) prescriber required and "
        "confirmed.", BODY)]

    flow += [Spacer(1, 12), Paragraph("__VERDICT_HINT_APPROVE__", SMALL)]
    doc.build(flow)
    print("wrote:", OUT / "04_APPROVE_hepc_daa_genotype1.pdf")


# ============================================================================
# Hepatitis C / liver-disease policy bundle (ingest into /policies)
# ============================================================================
def policy_hepc():
    doc = SimpleDocTemplate(str(OUT / "policy_aetna_hcv_daa.pdf"),
                            pagesize=LETTER, leftMargin=0.7*inch, rightMargin=0.7*inch)
    flow = []
    flow += [Paragraph("AETNA CLINICAL POLICY BULLETIN", H1),
             Paragraph("CPB 0860 — Direct-Acting Antivirals (DAAs) for Hepatitis C Virus", H2),
             Paragraph("Effective 2026-01-01 · Last reviewed 2026-04 · Replaces CPB 0860 (2025-09)", SMALL),
             Spacer(1, 12)]

    flow += section("§I. Scope")
    flow += [Paragraph(
        "This policy covers prior-authorization criteria for direct-acting antiviral (DAA) therapy of "
        "chronic hepatitis C virus (HCV) infection. Drugs in scope: sofosbuvir/velpatasvir, "
        "glecaprevir/pibrentasvir, ledipasvir/sofosbuvir, sofosbuvir/velpatasvir/voxilaprevir, and "
        "elbasvir/grazoprevir.", BODY)]

    flow += section("§II. Medical necessity criteria (must meet ALL)")
    flow += [Paragraph(
        "<b>1. Confirmed chronic HCV infection</b> &mdash; positive HCV RNA persisting ≥ 6 months, "
        "with documented genotype.<br/>"
        "<b>2. Liver disease assessment</b> &mdash; FibroScan, FibroSure, or biopsy-staged fibrosis "
        "(METAVIR F0&ndash;F4 documented).<br/>"
        "<b>3. Co-infection screening</b> &mdash; HBV (HBsAg, anti-HBc) and HIV testing completed and "
        "results documented.<br/>"
        "<b>4. Drug interaction screening</b> &mdash; contraindicated medications (amiodarone, certain "
        "anticonvulsants, certain anti-retrovirals) reviewed and addressed.<br/>"
        "<b>5. Specialist prescriber</b> &mdash; hepatology, gastroenterology, infectious disease, or "
        "trained mid-level under specialist supervision.", BODY)]

    flow += section("§III. Genotype-specific regimen selection (Category 1 evidence per AASLD-IDSA 2024)")
    flow += [Paragraph(
        "<b>Genotype 1a/1b, treatment-naive, non-cirrhotic:</b> sofosbuvir/velpatasvir 12 wk (preferred), "
        "or glecaprevir/pibrentasvir 8 wk.<br/>"
        "<b>Genotype 1, compensated cirrhosis:</b> sofosbuvir/velpatasvir 12 wk.<br/>"
        "<b>Genotype 2, 3, 5, 6, treatment-naive:</b> sofosbuvir/velpatasvir 12 wk (pan-genotypic).<br/>"
        "<b>Genotype 4:</b> sofosbuvir/velpatasvir 12 wk OR ledipasvir/sofosbuvir 12 wk.<br/>"
        "<b>Treatment-experienced or decompensated cirrhosis:</b> defer to specialist; ribavirin "
        "augmentation may be required.", BODY)]

    flow += section("§IV. Liver transplant candidates")
    flow += [Paragraph(
        "DAA therapy peri-transplant is medically necessary for HCV-positive transplant candidates. "
        "Pre-transplant treatment is preferred when MELD &lt; 21 to maximize SVR rates. Post-transplant "
        "treatment requires drug-drug interaction screening with calcineurin inhibitors (tacrolimus, "
        "cyclosporine).", BODY)]

    flow += section("§V. Documentation required for adjudication")
    flow += [Paragraph(
        "1. Genotype + viral load report.<br/>"
        "2. FibroScan / FibroSure or biopsy result.<br/>"
        "3. HBV / HIV serology.<br/>"
        "4. Specialist prescriber NPI + consult note.<br/>"
        "5. Drug-interaction screening checklist signed by prescriber.", BODY)]

    flow += section("§VI. References")
    flow += [Paragraph(
        "AASLD-IDSA HCV Guidance (https://www.hcvguidelines.org/) &middot; "
        "ASTRAL-1, ASTRAL-2, ASTRAL-3 trials (NEJM 2015) &middot; "
        "FDA Epclusa label, revised 2024-09 &middot; "
        "Aetna previous CPB 0860 (2025-09).", SMALL)]

    doc.build(flow)
    print("wrote:", OUT / "policy_aetna_hcv_daa.pdf")


# ============================================================================
# Liver transplantation policy
# ============================================================================
def policy_liver_transplant():
    doc = SimpleDocTemplate(str(OUT / "policy_aetna_liver_transplant.pdf"),
                            pagesize=LETTER, leftMargin=0.7*inch, rightMargin=0.7*inch)
    flow = []
    flow += [Paragraph("AETNA CLINICAL POLICY BULLETIN", H1),
             Paragraph("CPB 0596 — Liver Transplantation (Adult Orthotopic)", H2),
             Paragraph("Effective 2026-01-01 · Last reviewed 2026-03", SMALL),
             Spacer(1, 12)]

    flow += section("§I. Scope")
    flow += [Paragraph(
        "Aetna covers adult orthotopic liver transplantation for medically necessary indications when "
        "performed at a UNOS-approved transplant center. Living-donor and deceased-donor procedures "
        "are both in scope. This policy aligns with OPTN policy 9 and AASLD 2024 transplant guidance.",
        BODY)]

    flow += section("§II. Medical necessity criteria (any qualifies)")
    flow += [Paragraph(
        "<b>A. End-stage liver disease (ESLD)</b> with one or more:<br/>"
        "&nbsp;&nbsp;1. MELD-Na score ≥ 15<br/>"
        "&nbsp;&nbsp;2. Decompensated cirrhosis (variceal bleed, ascites, hepatic encephalopathy, "
        "spontaneous bacterial peritonitis)<br/>"
        "&nbsp;&nbsp;3. Refractory hepatic hydrothorax<br/>"
        "<b>B. Hepatocellular carcinoma (HCC)</b> meeting Milan criteria (single tumor ≤ 5 cm OR "
        "up to 3 tumors each ≤ 3 cm, no extrahepatic spread, no major vascular invasion).<br/>"
        "<b>C. Acute liver failure</b> (King's College or Clichy criteria met).<br/>"
        "<b>D. Genetic / metabolic indications</b> &mdash; Wilson's disease, hereditary hemochromatosis, "
        "α1-antitrypsin deficiency, primary hyperoxaluria.", BODY)]

    flow += section("§III. Required pre-transplant workup")
    flow += [Paragraph(
        "1. MELD-Na within 90 days of listing.<br/>"
        "2. Cardiac clearance (stress echo or coronary angiography per age/risk).<br/>"
        "3. Pulmonary clearance (PFTs, room-air ABG; rule out hepatopulmonary syndrome and "
        "porto-pulmonary hypertension).<br/>"
        "4. Renal function assessment (eGFR, urinalysis).<br/>"
        "5. Infectious screening: HBV, HCV, HIV, CMV, EBV, VZV, syphilis, latent TB.<br/>"
        "6. Cancer screening per age/risk.<br/>"
        "7. Psychosocial evaluation by transplant social worker.<br/>"
        "8. <b>Substance use:</b> documented abstinence per program criteria (commonly ≥ 6 months "
        "for alcohol; varies by center). 6-month rule may be waived for severe alcohol-associated "
        "hepatitis with multidisciplinary review per AASLD 2018 recommendations.", BODY)]

    flow += section("§IV. Allocation principles")
    flow += [Paragraph(
        "MELD-Na is the primary allocation score. Standardized exception points are applied for HCC "
        "(MMaT-3), pulmonary complications, and selected metabolic/cholestatic conditions per OPTN "
        "policy 9.", BODY)]

    flow += section("§V. Post-transplant immunosuppression")
    flow += [Paragraph(
        "Standard initial regimen: tacrolimus + mycophenolate ± corticosteroids. mTOR inhibitors "
        "(everolimus, sirolimus) considered for HCC indication or renal-sparing. Drug-drug "
        "interactions with HCV DAAs must be screened (see CPB 0860).", BODY)]

    flow += section("§VI. References")
    flow += [Paragraph(
        "OPTN policy 9 &middot; AASLD 2024 transplant guidance &middot; "
        "MELD-Na allocation (NEJM 2008) &middot; Milan criteria (NEJM 1996).", SMALL)]

    doc.build(flow)
    print("wrote:", OUT / "policy_aetna_liver_transplant.pdf")


if __name__ == "__main__":
    case_approve()
    case_deny()
    case_refer()
    case_hepc()
    policy_hepc()
    policy_liver_transplant()
    print("\nAll PDFs written to:", OUT)
