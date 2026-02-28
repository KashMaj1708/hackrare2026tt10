"""
Phase 5: Layer 4 - Evidence provenance.
Classify edge evidence type and score.
"""
import pandas as pd

from .config import get_paths

EVIDENCE_HIERARCHY = {"clinical_trial": 4, "human_genetic": 3, "preclinical": 2, "computational": 1, "curated_database": 3}

SOURCE_TO_EVIDENCE = {
    "drugbank": "curated_database",
    "reactome": "curated_database",
    "disgenet": "computational",
    "gwas catalog": "human_genetic",
    "gwascatalog": "human_genetic",
    "clinvar": "human_genetic",
    "omim": "human_genetic",
    "ctd": "computational",
    "string": "preclinical",
    "text-mining": "computational",
}


def evidence_type_from_source(source: str) -> str:
    s = (source or "").lower()
    for key, ev in SOURCE_TO_EVIDENCE.items():
        if key in s:
            return ev
    return "computational"


def evidence_score_from_type(ev_type: str) -> float:
    return EVIDENCE_HIERARCHY.get(ev_type, 1) / 4.0


def run_phase5(kg: pd.DataFrame = None, save: bool = True) -> pd.DataFrame:
    paths = get_paths()
    if kg is None:
        p = paths.processed / "primekg_full.csv"
        if not p.exists():
            return pd.DataFrame(columns=["relation", "evidence_type", "evidence_score"])
        kg = pd.read_csv(p)
    src_col = "x_source" if "x_source" in kg.columns else "source"
    if src_col not in kg.columns:
        kg["evidence_type"] = "computational"
        kg["evidence_score"] = 0.25
    else:
        kg["evidence_type"] = kg[src_col].astype(str).apply(evidence_type_from_source)
        kg["evidence_score"] = kg["evidence_type"].apply(evidence_score_from_type)
    if save:
        paths.processed.mkdir(parents=True, exist_ok=True)
        kg.to_csv(paths.processed / "primekg_with_evidence.csv", index=False)
    return kg
