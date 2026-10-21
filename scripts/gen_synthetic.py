"""Generate a small synthetic regulatory corpus as real PDFs, plus ground truth.

All companies, products and people are fictional. Planted facts (excipient grades,
spec contradictions, commitments, due dates) are recorded in ground_truth.json so
the extraction can be scored.
"""
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT = Path(__file__).resolve().parents[1] / "data" / "synthetic"
SS = getSampleStyleSheet()
H1, H2, BODY = SS["Heading1"], SS["Heading2"], SS["BodyText"]
COMPANY = "Halden Therapeutics, Inc."

BOILER = (
    "This section is provided in accordance with the Common Technical Document format. "
    "Information herein is confidential and proprietary to {company}. Batch records "
    "referenced in this section are available for inspection at the manufacturing site."
)


def build(path: Path, flow: list) -> None:
    doc = SimpleDocTemplate(str(path), pagesize=letter, leftMargin=inch, rightMargin=inch,
                            topMargin=inch, bottomMargin=inch)
    doc.build(flow)


def p(text: str, style=BODY):
    return Paragraph(text, style)


def table(rows: list[list[str]]):
    t = Table(rows, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


# ---------------------------------------------------------------- CMC sections
CMC = [
    dict(product="HT-101", name="Halvorex (ivaltrine) 50 mg tablets",
         excipients=[("Microcrystalline cellulose", "Avicel PH-102, NF", "Filler/binder"),
                     ("Croscarmellose sodium", "Ac-Di-Sol, NF", "Disintegrant"),
                     ("Magnesium stearate", "NF, vegetable source", "Lubricant")],
         justification="Avicel PH-102 was selected over PH-101 because its larger median particle size "
                       "(approximately 100 um) provides superior powder flow for direct compression at "
                       "commercial press speeds; three engineering batches showed weight variation below 1.5% RSD.",
         guidance=["ICH Q8(R2) Pharmaceutical Development", "USP-NF monograph for Microcrystalline Cellulose"]),
    dict(product="HT-204", name="Corvala (setrapine) 10 mg tablets",
         excipients=[("Microcrystalline cellulose", "Avicel PH-101, NF", "Filler"),
                     ("Lactose monohydrate", "Fast-Flo 316, NF", "Filler"),
                     ("Magnesium stearate", "NF, vegetable source", "Lubricant")],
         justification="Avicel PH-101 was chosen for its finer particle size, which improves content uniformity "
                       "of the low-dose active in the wet granulation process. Blend uniformity across "
                       "development batches met the acceptance criterion of 90.0-110.0%.",
         guidance=["ICH Q8(R2) Pharmaceutical Development", "ICH Q6A Specifications",
                   "FDA Guidance for Industry: Nonclinical Studies for the Safety Evaluation of Pharmaceutical Excipients"]),
    dict(product="HT-317", name="Brexidol (tamorastat) 25 mg capsules",
         excipients=[("Pregelatinized starch", "Starch 1500, NF", "Filler/disintegrant"),
                     ("Colloidal silicon dioxide", "Aerosil 200, NF", "Glidant"),
                     ("Magnesium stearate", "NF, vegetable source", "Lubricant")],
         justification="Starch 1500 was selected because its partial pregelatinization provides both filling and "
                       "disintegration function in a single excipient, minimizing the number of components in "
                       "the capsule fill. Dissolution exceeded 85% in 30 minutes for all registration batches.",
         guidance=["ICH Q8(R2) Pharmaceutical Development", "Ph. Eur. monograph 1267 Pregelatinised Starch"]),
    dict(product="HT-422", name="Nurivan (olcetrine) 100 mg tablets",
         excipients=[("Lactose monohydrate", "Ph. Eur., milled grade 200 mesh", "Filler"),
                     ("Povidone", "K30, Ph. Eur.", "Binder"),
                     ("Sodium stearyl fumarate", "PRUV, NF", "Lubricant")],
         justification="Milled lactose monohydrate (200 mesh) was used because it is the grade qualified at the "
                       "European contract manufacturer and is compatible with the aqueous granulation process. "
                       "Compatibility studies at 40C/75% RH for 3 months showed no increase in degradants.",
         guidance=["ICH Q8(R2) Pharmaceutical Development", "EMA Guideline on Excipients in the Dossier for "
                   "Application for Marketing Authorisation of a Medicinal Product"]),
    dict(product="HT-509", name="Pellira (dunaxitib) 20 mg/mL oral solution",
         excipients=[("Polysorbate 80", "Super Refined, low peroxide, NF", "Solubilizer"),
                     ("Sucralose", "NF", "Sweetener"),
                     ("Sodium benzoate", "NF", "Preservative")],
         justification="A low-peroxide grade of polysorbate 80 was required because dunaxitib is susceptible to "
                       "oxidative degradation; standard grade lots produced oxidative degradant D-3 above the "
                       "0.2% identification threshold at 6 months accelerated.",
         guidance=["ICH Q8(R2) Pharmaceutical Development", "ICH Q3B(R2) Impurities in New Drug Products"]),
    dict(product="HT-611", name="Zentaro (fimolast) 5 mg orally disintegrating tablets",
         excipients=[("Mannitol", "Pearlitol 200 SD, USP", "Filler"),
                     ("Crospovidone", "Polyplasdone XL-10, NF", "Superdisintegrant"),
                     ("Magnesium stearate", "NF, vegetable source", "Lubricant")],
         justification="Spray-dried mannitol (Pearlitol 200 SD) was selected for its pleasant mouthfeel and "
                       "compressibility, enabling disintegration in under 30 seconds per USP <701>.",
         guidance=["FDA Guidance for Industry: Orally Disintegrating Tablets", "ICH Q8(R2) Pharmaceutical Development"]),
]

# Current approved excipient spec. Two planted contradictions: HT-204 MCC grade, HT-422 lactose grade.
SPEC = {
    "HT-101": [("Microcrystalline cellulose", "Avicel PH-102, NF"), ("Croscarmellose sodium", "NF"),
               ("Magnesium stearate", "NF, vegetable source")],
    "HT-204": [("Microcrystalline cellulose", "Avicel PH-102, NF"), ("Lactose monohydrate", "Fast-Flo 316, NF"),
               ("Magnesium stearate", "NF, vegetable source")],
    "HT-317": [("Pregelatinized starch", "Starch 1500, NF"), ("Colloidal silicon dioxide", "NF"),
               ("Magnesium stearate", "NF, vegetable source")],
    "HT-422": [("Lactose", "Anhydrous, direct compression grade, NF"), ("Povidone", "K30"),
               ("Sodium stearyl fumarate", "NF")],
    "HT-509": [("Polysorbate 80", "Low peroxide grade, NF"), ("Sucralose", "NF"), ("Sodium benzoate", "NF")],
    "HT-611": [("Mannitol", "Spray-dried, USP"), ("Crospovidone", "NF"), ("Magnesium stearate", "NF")],
}
CONTRADICTIONS = {
    "HT-204": "Submission uses Avicel PH-101; current spec requires Avicel PH-102.",
    "HT-422": "Submission uses milled lactose monohydrate (Ph. Eur.); current spec requires anhydrous lactose NF.",
}


def gen_cmc(gt: dict) -> None:
    for c in CMC:
        fn = f"cmc_{c['product']}_3.2.P.pdf"
        flow = [p(f"Module 3.2.P Drug Product: {c['name']}", H1),
                p(f"Applicant: {COMPANY} &nbsp;&nbsp; Product code: {c['product']}"),
                p(BOILER.format(company=COMPANY)), Spacer(1, 12),
                p("3.2.P.1 Description and Composition of the Drug Product", H2),
                p(f"{c['name']} are manufactured using the excipients listed below. All excipients comply "
                  f"with the referenced compendial monographs."),
                table([["Excipient", "Grade", "Function"]] + [list(e) for e in c["excipients"]]),
                Spacer(1, 12),
                p("3.2.P.2 Pharmaceutical Development", H2),
                p("3.2.P.2.1.2 Excipients", H2),
                p(c["justification"]),
                p("The selection of all excipients and their grades followed a science- and risk-based "
                  "approach. The following guidance was considered: " + "; ".join(c["guidance"]) + "."),
                Spacer(1, 12),
                p("3.2.P.4 Control of Excipients", H2),
                p("Excipients are tested on receipt against the current compendial monograph and the "
                  "applicant's internal excipient specification. Certificates of analysis from qualified "
                  "suppliers are reviewed by Quality Assurance prior to release."),
                p("3.2.P.5 Control of Drug Product", H2),
                p("Release testing includes appearance, identification by HPLC, assay (95.0-105.0%), "
                  "related substances, dissolution and uniformity of dosage units.")]
        build(OUT / fn, flow)
        gt[fn] = {"doc_type": "cmc", "product": c["product"],
                  "excipient_grades": [f"{e[0]}: {e[1]}" for e in c["excipients"]],
                  "grade_justification": c["justification"], "guidance_cited": c["guidance"],
                  "contradicts_spec": c["product"] in CONTRADICTIONS,
                  "contradiction_detail": CONTRADICTIONS.get(c["product"])}


def gen_spec(gt: dict) -> None:
    fn = "spec_ES-2026-03_current_excipient_specification.pdf"
    flow = [p("Current Approved Excipient Specification ES-2026-03", H1),
            p(f"{COMPANY} Quality Assurance. Effective date: 2026-03-01. Supersedes ES-2024-11."),
            p("This document defines the approved excipient grades for each commercial product. Any use of "
              "a grade not listed here requires a change control and, where applicable, a regulatory variation.")]
    for prod, rows in SPEC.items():
        flow += [p(f"Product {prod}", H2), table([["Excipient", "Approved grade"]] + [list(r) for r in rows])]
    build(OUT / fn, flow)
    gt[fn] = {"doc_type": "spec"}


# ---------------------------------------------------------------- HA letters
LETTERS = [
    dict(id="FDA-2025-0412", agency="U.S. Food and Drug Administration", product="HT-101", date="2025-04-12",
         commitment="submit the final 36-month long-term stability data for three commercial-scale batches of "
                    "Halvorex 50 mg tablets", due="2026-06-30", owner="Dr. Priya Raman, CMC Regulatory Lead"),
    dict(id="EMA-2025-0907", agency="European Medicines Agency", product="HT-422", date="2025-09-07",
         commitment="provide a validated method for nitrosamine impurity N-nitroso-olcetrine with a limit "
                    "of quantitation at or below 30 ng/day equivalent", due="2026-03-31", owner=None),
    dict(id="FDA-2025-1120", agency="U.S. Food and Drug Administration", product="HT-509", date="2025-11-20",
         commitment="conduct an in-use stability study of the opened bottle over 60 days under patient-use "
                    "conditions", due="2026-09-30", owner="Marcus Ode, Analytical Development"),
    dict(id="PMDA-2026-0115", agency="Pharmaceuticals and Medical Devices Agency (Japan)", product="HT-317",
         date="2026-01-15", commitment="submit dissolution profile comparison data (f2) between the "
                                       "registration and the proposed commercial capsule shell supplier",
         due="2026-07-15", owner=None),
    dict(id="FDA-2026-0302", agency="U.S. Food and Drug Administration", product="HT-611", date="2026-03-02",
         commitment="revise the disintegration acceptance criterion to NMT 30 seconds and submit the updated "
                    "specification in a CBE-30 supplement", due="2026-05-01", owner="Dr. Priya Raman, CMC Regulatory Lead"),
]


def gen_letters(gt: dict) -> None:
    for l in LETTERS:
        fn = f"ha_letter_{l['id']}.pdf"
        owner_line = (f"Applicant contact for this commitment: {l['owner']}." if l["owner"] else
                      "Please direct questions regarding this letter to the Regulatory Project Manager.")
        flow = [p(l["agency"], H1), p(f"Reference: {l['id']} &nbsp;&nbsp; Date: {l['date']}"),
                p(f"To: {COMPANY}, Regulatory Affairs"), Spacer(1, 12),
                p(f"Subject: Post-approval commitment for product {l['product']}", H2),
                p("We have completed our review of your submission and acknowledge your response to our "
                  "information request. Following discussion, you have agreed to the following commitment."),
                p(f"Commitment: You committed to {l['commitment']}."),
                p(f"Due date: The final report for this commitment should be submitted no later than {l['due']}."),
                p("Failure to fulfil this commitment may result in further regulatory action. Please submit "
                  "the requested information as an amendment referencing this letter."),
                p(owner_line), Spacer(1, 24), p("Sincerely,"), p("Division of Pharmaceutical Quality")]
        build(OUT / fn, flow)
        # Whether a commitment was met is never stated in the letter itself: expected not_found.
        gt[fn] = {"doc_type": "ha_letter", "product": l["product"], "commitment": l["commitment"],
                  "due_date": l["due"], "met": None, "owner": l["owner"]}


# ---------------------------------------------------------------- Stability protocols
PROTOCOLS = [
    dict(id="SP-101-02", product="HT-101", conditions="25C/60% RH (long-term) and 40C/75% RH (accelerated)",
         timepoints="0, 3, 6, 9, 12, 18, 24, 36 months (long-term); 0, 3, 6 months (accelerated)",
         criteria="Assay 95.0-105.0%; any unspecified degradant NMT 0.2%; total degradants NMT 1.0%; "
                  "dissolution Q=80% at 30 minutes",
         deviation="Deviation DEV-2025-118: the 9-month long-term pull was performed 6 days late due to chamber "
                   "maintenance; impact assessed as none.",
         bracketing="Bracketing is applied to the 30-count and 500-count HDPE bottle presentations; the 90-count "
                    "presentation is not tested because container closure and fill ratio fall within the bracket.",
         commitment="The first three commercial batches will be placed on long-term stability post-approval and "
                    "one batch per year thereafter."),
    dict(id="SP-204-01", product="HT-204", conditions="30C/75% RH (long-term, Zone IVb) and 40C/75% RH (accelerated)",
         timepoints="0, 3, 6, 9, 12, 18, 24 months (long-term); 0, 1, 3, 6 months (accelerated)",
         criteria="Assay 90.0-110.0%; impurity S-2 NMT 0.5%; water content NMT 5.0%",
         deviation="No deviations have been recorded to date.",
         bracketing="Bracketing is not applied; all strengths and pack sizes are tested.",
         commitment="One production batch per year will be added to the annual stability program."),
    dict(id="SP-509-03", product="HT-509", conditions="5C plus or minus 3C (long-term) and 25C/60% RH (accelerated)",
         timepoints="0, 3, 6, 9, 12, 18, 24 months (long-term); 0, 1, 3, 6 months (accelerated)",
         criteria="Assay 95.0-105.0%; oxidative degradant D-3 NMT 0.2%; pH 4.5-5.5; preservative content 80-110% of label",
         deviation="Deviation DEV-2026-022: refrigerator excursion to 11C for 4 hours on 2026-02-14; samples "
                   "retained and results evaluated as within specification.",
         bracketing="Bracketing is applied to the 60 mL and 240 mL bottle fills based on identical container "
                    "closure materials; the 120 mL fill is bracketed.",
         commitment="The in-use stability study requested under FDA-2025-1120 will be conducted on the first "
                    "commercial batch."),
    dict(id="SP-611-01", product="HT-611", conditions="25C/60% RH (long-term), 30C/65% RH (intermediate) and 40C/75% RH (accelerated)",
         timepoints="0, 3, 6, 9, 12, 18, 24 months (long-term); 0, 6, 12 months (intermediate); 0, 3, 6 months (accelerated)",
         criteria="Assay 95.0-105.0%; disintegration NMT 30 seconds; hardness 20-40 N; total degradants NMT 1.5%",
         deviation="No deviations have been recorded to date.",
         bracketing="Matrixing, rather than bracketing, is applied across blister strengths per ICH Q1D.",
         commitment="None stated beyond the routine annual batch placement."),
]


def gen_protocols(gt: dict) -> None:
    for s in PROTOCOLS:
        fn = f"stability_protocol_{s['id']}.pdf"
        flow = [p(f"Stability Protocol {s['id']}", H1), p(f"Product: {s['product']} &nbsp;&nbsp; Sponsor: {COMPANY}"),
                p("This protocol is designed in accordance with ICH Q1A(R2) Stability Testing of New Drug "
                  "Substances and Products."), Spacer(1, 12),
                p("1. Storage Conditions", H2), p(f"Samples will be stored at {s['conditions']}."),
                p("2. Testing Timepoints", H2), p(f"Samples will be pulled at {s['timepoints']}."),
                p("3. Acceptance Criteria", H2), p(s["criteria"] + "."),
                p("4. Deviations", H2), p(s["deviation"]),
                p("5. Bracketing and Matrixing", H2), p(s["bracketing"]),
                p("6. Post-Approval Stability Commitment", H2), p(s["commitment"])]
        build(OUT / fn, flow)
        gt[fn] = {"doc_type": "stability_protocol", "product": s["product"], "storage_condition": s["conditions"],
                  "timepoints": s["timepoints"], "acceptance_criteria": s["criteria"], "deviations": s["deviation"],
                  "bracketing_justification": s["bracketing"], "post_approval_commitment": s["commitment"]}


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    gt: dict = {}
    gen_cmc(gt)
    gen_spec(gt)
    gen_letters(gt)
    gen_protocols(gt)
    (OUT / "ground_truth.json").write_text(json.dumps(gt, indent=2))
    print(f"wrote {len(gt)} PDFs to {OUT}")
