"""
Phase 4: Layer 3 - Safety and pharmacology (DrugBank + SIDER).
Drug-target action types and safety flags.
"""
from pathlib import Path
import xml.etree.ElementTree as ET
import pandas as pd

from .config import get_paths

NS = {"db": "http://www.drugbank.ca"}

SAFETY_CATEGORIES = {
    "hepatotoxicity": ["hepatic failure", "hepatotoxicity", "liver injury", "jaundice"],
    "cardiotoxicity": ["qt prolongation", "cardiac arrest", "arrhythmia", "heart failure"],
    "nephrotoxicity": ["renal failure", "nephrotoxicity", "kidney injury"],
    "neurotoxicity": ["seizure", "neuropathy", "encephalopathy"],
    "hematotoxicity": ["agranulocytosis", "pancytopenia", "thrombocytopenia"],
    "immunosuppression": ["immunosuppression", "opportunistic infection"],
    "teratogenicity": ["teratogenic", "birth defect", "pregnancy category x"],
    "pediatric_risk": ["not recommended in children", "pediatric death", "growth retardation"],
}


def parse_drugbank_xml(xml_path: Path) -> tuple:
    if not xml_path.exists():
        return [], []
    drug_targets = []
    drug_safety = []
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for drug in root.findall(".//db:drug", NS):
            primary_id = drug.find('db:drugbank-id[@primary="true"]', NS)
            drugbank_id = (primary_id.text or "").strip() if primary_id is not None else None
            name_el = drug.find("db:name", NS)
            name = (name_el.text or "").strip() if name_el is not None else ""
            for target in drug.findall(".//db:targets/db:target", NS):
                gene_el = target.find(".//db:gene-name", NS)
                actions_el = target.findall(".//db:actions/db:action", NS)
                actions = [(a.text or "").strip() for a in actions_el if a.text]
                known_el = target.find(".//db:known-action", NS)
                known = (known_el.text or "").strip() if known_el is not None and known_el.text else "unknown"
                if gene_el is not None and gene_el.text and drugbank_id:
                    drug_targets.append({
                        "drugbank_id": drugbank_id,
                        "drug_name": name,
                        "gene_symbol": (gene_el.text or "").strip(),
                        "actions": actions,
                        "known_action": known,
                    })
            contra_el = drug.find("db:contraindications", NS)
            contra = (contra_el.text or "").lower() if contra_el is not None and contra_el.text else ""
            preg_el = drug.find(".//db:pregnancy-category", NS)
            preg = (preg_el.text or "").lower() if preg_el is not None and preg_el.text else ""
            drug_safety.append({
                "drugbank_id": drugbank_id,
                "drug_name": name,
                "contraindications_text": contra,
                "pregnancy_category": preg,
            })
    except ET.ParseError:
        pass
    return drug_targets, drug_safety


def classify_safety_flags(contra_text: str) -> list:
    text = (contra_text or "").lower()
    return [cat for cat, keywords in SAFETY_CATEGORIES.items() if any(kw in text for kw in keywords)]


def run_phase4(save: bool = True) -> tuple:
    paths = get_paths()
    xml_path = paths.raw_drugbank / "full_database.xml"
    if not xml_path.exists():
        for f in paths.raw_drugbank.glob("*.xml"):
            xml_path = f
            break
    drug_targets, drug_safety = parse_drugbank_xml(xml_path)
    drug_targets_df = pd.DataFrame(drug_targets) if drug_targets else pd.DataFrame(
        columns=["drugbank_id", "drug_name", "gene_symbol", "actions", "known_action"])
    drug_safety_df = pd.DataFrame(drug_safety) if drug_safety else pd.DataFrame(
        columns=["drugbank_id", "drug_name", "contraindications_text", "pregnancy_category"])
    if not drug_safety_df.empty and "contraindications_text" in drug_safety_df.columns:
        drug_safety_df["safety_flags"] = drug_safety_df["contraindications_text"].apply(classify_safety_flags)
    if save:
        paths.processed.mkdir(parents=True, exist_ok=True)
        drug_targets_df.to_csv(paths.processed / "drug_target_actions.csv", index=False)
        drug_safety_df.to_csv(paths.processed / "drug_safety.csv", index=False)
    return drug_targets_df, drug_safety_df
