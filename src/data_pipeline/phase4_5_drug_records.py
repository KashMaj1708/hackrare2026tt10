"""
Phase 4.5: Consolidated drug records.
Merge DrugBank targets/safety with additional fields: moa, description,
atc_codes, top_side_effects into one flat record per drug.
"""
import json
import xml.etree.ElementTree as ET
from pathlib import Path
import pandas as pd

from .config import get_paths

NS = {"db": "http://www.drugbank.ca"}


def _parse_drugbank_extended(xml_path: Path) -> dict:
    """Parse DrugBank XML for extended drug fields: moa, description, atc_codes, routes."""
    records = {}
    if not xml_path.exists():
        return records
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for drug in root.findall(".//db:drug", NS):
            primary_id = drug.find('db:drugbank-id[@primary="true"]', NS)
            drugbank_id = (primary_id.text or "").strip() if primary_id is not None else None
            if not drugbank_id:
                continue
            name_el = drug.find("db:name", NS)
            name = (name_el.text or "").strip() if name_el is not None else ""

            moa_el = drug.find("db:mechanism-of-action", NS)
            moa = (moa_el.text or "").strip() if moa_el is not None and moa_el.text else ""

            desc_el = drug.find("db:description", NS)
            description = (desc_el.text or "").strip() if desc_el is not None and desc_el.text else ""

            atc_codes = [a.get("code", a.text or "").strip()
                         for a in drug.findall(".//db:atc-codes/db:atc-code", NS)
                         if (a.get("code") or a.text)]

            drug_class = ""
            if atc_codes:
                drug_class = atc_codes[0][:5] if len(atc_codes[0]) >= 5 else atc_codes[0]

            route_els = drug.findall(".//db:routes/db:route", NS)
            routes = list({(r.text or "").strip() for r in route_els if r.text})
            if not routes:
                dosage_els = drug.findall(".//db:dosages/db:dosage/db:route", NS)
                routes = list({(r.text or "").strip() for r in dosage_els if r.text})

            # Targets
            targets = []
            for target in drug.findall(".//db:targets/db:target", NS):
                gene_el = target.find(".//db:gene-name", NS)
                if gene_el is None or not gene_el.text:
                    continue
                ncbi_el = target.find(".//db:polypeptide", NS)
                ncbi_id = ""
                if ncbi_el is not None:
                    src = ncbi_el.get("source")
                    ncbi_id = ncbi_el.get("id", "") if src and "ncbi" in src.lower() else ""
                actions_el = target.findall(".//db:actions/db:action", NS)
                action = ", ".join((a.text or "").strip() for a in actions_el if a.text) or "unknown"
                known_el = target.find(".//db:known-action", NS)
                known = (known_el.text or "").strip() if known_el is not None and known_el.text else "unknown"
                targets.append({
                    "gene": (gene_el.text or "").strip(),
                    "ncbi_id": ncbi_id,
                    "action": action,
                    "known_action": known,
                })

            # Safety flags from contraindications
            contra_el = drug.find("db:contraindications", NS)
            contra = (contra_el.text or "").lower() if contra_el is not None and contra_el.text else ""
            safety_flags = _classify_safety(contra)

            # Pediatric / pregnancy
            pediatric_safe = "not recommended in children" not in contra and "pediatric" not in contra
            preg_el = drug.find(".//db:pregnancy-category", NS)
            pregnancy_category = (preg_el.text or "").strip() if preg_el is not None and preg_el.text else ""

            records[drugbank_id] = {
                "drugbank_id": drugbank_id,
                "name": name,
                "drug_class": drug_class,
                "atc_codes": atc_codes,
                "moa": moa,
                "description": description,
                "targets": targets,
                "safety_flags": safety_flags,
                "pediatric_safe": pediatric_safe,
                "pregnancy_category": pregnancy_category,
                "routes": routes,
                "top_side_effects": [],  # filled from SIDER below
            }
    except ET.ParseError:
        pass
    return records


def _classify_safety(text: str) -> list:
    categories = {
        "hepatotoxicity": ["hepatic failure", "hepatotoxicity", "liver injury", "jaundice"],
        "cardiotoxicity": ["qt prolongation", "cardiac arrest", "arrhythmia", "heart failure"],
        "nephrotoxicity": ["renal failure", "nephrotoxicity", "kidney injury"],
        "neurotoxicity": ["seizure", "neuropathy", "encephalopathy"],
        "hematotoxicity": ["agranulocytosis", "pancytopenia", "thrombocytopenia"],
        "immunosuppression": ["immunosuppression", "opportunistic infection"],
        "teratogenicity": ["teratogenic", "birth defect", "pregnancy category x"],
        "pediatric_risk": ["not recommended in children", "pediatric death", "growth retardation"],
    }
    t = (text or "").lower()
    return [cat for cat, kws in categories.items() if any(kw in t for kw in kws)]


def _load_sider_side_effects(paths) -> dict:
    """Load SIDER side effects mapped via STITCH->PubChem->DrugBank.
    Returns {drugbank_id: [(se_name, frequency), ...]}."""
    se_map = {}
    sider_dir = paths.raw_sider
    # Try common SIDER file names
    for fname in ("meddra_all_se.tsv", "meddra_all_se.tsv.gz",
                  "meddra_freq.tsv", "meddra_freq.tsv.gz",
                  "side_effects.tsv"):
        p = sider_dir / fname
        if p.exists():
            try:
                df = pd.read_csv(p, sep="\t", header=None, low_memory=False)
                # SIDER format: STITCH_id, ... , side_effect_name, ...
                # We'll store raw and let downstream map
                for _, row in df.iterrows():
                    stitch = str(row.iloc[0]).strip()
                    se_name = str(row.iloc[-1]).strip() if len(row) > 1 else ""
                    freq = str(row.iloc[-2]).strip() if len(row) > 2 else "unknown"
                    if stitch not in se_map:
                        se_map[stitch] = []
                    se_map[stitch].append((se_name, freq))
            except Exception:
                continue
            break
    return se_map


def run_phase4_5(save: bool = True) -> pd.DataFrame:
    """Build consolidated drug records. Returns DataFrame."""
    paths = get_paths()

    # Try to parse DrugBank XML for extended fields
    xml_path = paths.raw_drugbank / "full_database.xml"
    if not xml_path.exists():
        for f in paths.raw_drugbank.glob("*.xml"):
            xml_path = f
            break
    records = _parse_drugbank_extended(xml_path)

    # If no DrugBank XML, build minimal records from existing processed tables
    if not records:
        targets_path = paths.processed / "drug_target_actions.csv"
        safety_path = paths.processed / "drug_safety.csv"
        drug_nodes_path = paths.processed / "drug_nodes.csv"

        drug_ids = set()
        if drug_nodes_path.exists():
            dn = pd.read_csv(drug_nodes_path)
            for _, row in dn.iterrows():
                did = str(row.get("node_id", ""))
                records[did] = {
                    "drugbank_id": did,
                    "name": str(row.get("node_name", "")),
                    "drug_class": "",
                    "atc_codes": [],
                    "moa": "",
                    "description": "",
                    "targets": [],
                    "safety_flags": [],
                    "pediatric_safe": True,
                    "pregnancy_category": "",
                    "routes": [],
                    "top_side_effects": [],
                }
                drug_ids.add(did)

        if targets_path.exists():
            ta = pd.read_csv(targets_path)
            for _, row in ta.iterrows():
                did = str(row.get("drugbank_id", ""))
                if did in records:
                    records[did]["targets"].append({
                        "gene": str(row.get("gene_symbol", "")),
                        "ncbi_id": "",
                        "action": str(row.get("actions", "unknown")),
                        "known_action": str(row.get("known_action", "unknown")),
                    })

        if safety_path.exists():
            ds = pd.read_csv(safety_path)
            for _, row in ds.iterrows():
                did = str(row.get("drugbank_id", ""))
                if did in records:
                    contra = str(row.get("contraindications_text", ""))
                    records[did]["safety_flags"] = _classify_safety(contra)
                    records[did]["pregnancy_category"] = str(row.get("pregnancy_category", ""))
                    records[did]["pediatric_safe"] = "not recommended in children" not in contra.lower()

    # Attach SIDER side effects
    sider_se = _load_sider_side_effects(paths)
    if sider_se:
        for did, rec in records.items():
            se = sider_se.get(did, [])
            # Keep top 10 by frequency
            rec["top_side_effects"] = se[:10]

    # Convert to DataFrame for saving
    rows = []
    for did, rec in records.items():
        rows.append({
            "drugbank_id": rec["drugbank_id"],
            "name": rec["name"],
            "drug_class": rec["drug_class"],
            "atc_codes": json.dumps(rec["atc_codes"]),
            "moa": rec["moa"],
            "description": rec["description"],
            "targets": json.dumps(rec["targets"]),
            "safety_flags": json.dumps(rec["safety_flags"]),
            "pediatric_safe": rec["pediatric_safe"],
            "pregnancy_category": rec["pregnancy_category"],
            "routes": json.dumps(rec["routes"]),
            "top_side_effects": json.dumps(rec["top_side_effects"]),
        })

    df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=[
        "drugbank_id", "name", "drug_class", "atc_codes", "moa", "description",
        "targets", "safety_flags", "pediatric_safe", "pregnancy_category",
        "routes", "top_side_effects",
    ])

    if save:
        paths.processed.mkdir(parents=True, exist_ok=True)
        df.to_csv(paths.processed / "drug_records_consolidated.csv", index=False)

    return df
