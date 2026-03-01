"""
Phase 1: Load and understand PrimeKG.
Extract disease-drug bipartite subgraph and node/edge tables.
"""
from pathlib import Path
import pandas as pd

from .config import get_paths

# Critical edge types for drug repurposing (plan 1.2)
DRUG_DISEASE_RELATIONS = ["indication", "contraindication", "off-label use"]


def find_kg_file(raw_primekg: Path) -> Path:
    """Find kg.csv, edges.csv, or similar in raw_primekg."""
    for name in ("kg.csv", "edges.csv", "primekg.csv", "kg_sample.csv"):
        p = raw_primekg / name
        if p.exists():
            return p
    raise FileNotFoundError(
        f"No PrimeKG CSV found in {raw_primekg}. "
        "Download from Harvard Dataverse (doi:10.7910/DVN/IXA7BM) and place kg.csv (or edges.csv) there."
    )


def load_kg(raw_primekg: Path = None) -> pd.DataFrame:
    paths = get_paths()
    raw_primekg = raw_primekg or paths.raw_primekg
    kg_path = find_kg_file(raw_primekg)
    kg = pd.read_csv(kg_path)
    return kg


def get_drug_disease_edges(kg: pd.DataFrame) -> pd.DataFrame:
    """All drug-disease edges (indication, contraindication, off-label use). Vectorized."""
    empty = pd.DataFrame(columns=[
        "relation", "drug_index", "drug_id", "drug_name",
        "disease_index", "disease_id", "disease_name"
    ])
    rel_col = "relation" if "relation" in kg.columns else "display_relation"
    if rel_col not in kg.columns:
        return empty
    rel_mask = kg[rel_col].isin(DRUG_DISEASE_RELATIONS)
    subset = kg[rel_mask].copy()
    if subset.empty:
        return empty
    x_type_lower = subset["x_type"].astype(str).str.lower()
    y_type_lower = subset["y_type"].astype(str).str.lower()
    # Case 1: x=drug, y=disease
    mask1 = x_type_lower.str.contains("drug", na=False) & y_type_lower.str.contains("disease", na=False)
    df1 = subset.loc[mask1, [rel_col, "x_index", "x_id", "x_name", "y_index", "y_id", "y_name"]].copy()
    df1.columns = ["relation", "drug_index", "drug_id", "drug_name", "disease_index", "disease_id", "disease_name"]
    # Case 2: x=disease, y=drug
    mask2 = x_type_lower.str.contains("disease", na=False) & y_type_lower.str.contains("drug", na=False)
    df2 = subset.loc[mask2, [rel_col, "y_index", "y_id", "y_name", "x_index", "x_id", "x_name"]].copy()
    df2.columns = ["relation", "drug_index", "drug_id", "drug_name", "disease_index", "disease_id", "disease_name"]
    result = pd.concat([df1, df2], ignore_index=True)
    return result if len(result) > 0 else empty


def get_disease_nodes(kg: pd.DataFrame) -> pd.DataFrame:
    """Unique disease nodes from kg."""
    mask = kg["x_type"].astype(str).str.lower().str.contains("disease", na=False)
    df = kg.loc[mask, ["x_index", "x_id", "x_name"]].drop_duplicates()
    df = df.rename(columns={"x_index": "node_index", "x_id": "node_id", "x_name": "node_name"})
    # Also from y_type
    mask_y = kg["y_type"].astype(str).str.lower().str.contains("disease", na=False)
    df2 = kg.loc[mask_y, ["y_index", "y_id", "y_name"]].drop_duplicates()
    df2 = df2.rename(columns={"y_index": "node_index", "y_id": "node_id", "y_name": "node_name"})
    return pd.concat([df, df2], ignore_index=True).drop_duplicates(subset=["node_index"])


def get_drug_nodes(kg: pd.DataFrame) -> pd.DataFrame:
    """Unique drug nodes from kg."""
    mask = kg["x_type"].astype(str).str.lower().str.contains("drug", na=False)
    df = kg.loc[mask, ["x_index", "x_id", "x_name"]].drop_duplicates()
    df = df.rename(columns={"x_index": "node_index", "x_id": "node_id", "x_name": "node_name"})
    mask_y = kg["y_type"].astype(str).str.lower().str.contains("drug", na=False)
    df2 = kg.loc[mask_y, ["y_index", "y_id", "y_name"]].drop_duplicates()
    df2 = df2.rename(columns={"y_index": "node_index", "y_id": "node_id", "y_name": "node_name"})
    return pd.concat([df, df2], ignore_index=True).drop_duplicates(subset=["node_index"])


def run_phase1(save_processed: bool = True) -> tuple:
    """Load PrimeKG, extract drug-disease subgraph, optionally save. Returns (kg, drug_disease_edges, disease_nodes, drug_nodes)."""
    paths = get_paths()
    kg = load_kg()
    drug_disease = get_drug_disease_edges(kg)
    disease_nodes = get_disease_nodes(kg)
    drug_nodes = get_drug_nodes(kg)

    if save_processed:
        paths.processed.mkdir(parents=True, exist_ok=True)
        kg.to_csv(paths.processed / "primekg_full.csv", index=False)
        drug_disease.to_csv(paths.processed / "drug_disease_edges.csv", index=False)
        disease_nodes.to_csv(paths.processed / "disease_nodes.csv", index=False)
        drug_nodes.to_csv(paths.processed / "drug_nodes.csv", index=False)

    return kg, drug_disease, disease_nodes, drug_nodes
