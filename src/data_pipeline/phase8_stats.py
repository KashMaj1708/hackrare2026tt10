"""
Phase 8: Dataset statistics to report after construction.
"""
import pickle
from pathlib import Path
import pandas as pd
import networkx as nx

from .config import get_paths


def run_phase8(save: bool = True) -> dict:
    paths = get_paths()
    stats = {}
    if (paths.processed / "primekg_full.csv").exists():
        kg = pd.read_csv(paths.processed / "primekg_full.csv")
        stats["total_edges"] = len(kg)
        stats["unique_relations"] = kg["relation"].nunique() if "relation" in kg.columns else 0
    if (paths.processed / "disease_nodes.csv").exists():
        dn = pd.read_csv(paths.processed / "disease_nodes.csv")
        stats["total_disease_nodes"] = len(dn)
    if (paths.processed / "drug_nodes.csv").exists():
        dr = pd.read_csv(paths.processed / "drug_nodes.csv")
        stats["total_drug_nodes"] = len(dr)
    if (paths.processed / "disease_rare_mask.csv").exists():
        rm = pd.read_csv(paths.processed / "disease_rare_mask.csv")
        stats["rare_disease_nodes"] = int(rm["is_rare"].sum()) if "is_rare" in rm.columns else 0
    if (paths.enriched / "candidates_positives.csv").exists():
        pos = pd.read_csv(paths.enriched / "candidates_positives.csv")
        stats["positive_indication_edges_rare"] = len(pos)
    if (paths.enriched / "candidates_negatives_hard.csv").exists():
        neg = pd.read_csv(paths.enriched / "candidates_negatives_hard.csv")
        stats["contraindication_edges_rare"] = len(neg)
    if (paths.enriched / "enriched_graph.gpickle").exists():
        with open(paths.enriched / "enriched_graph.gpickle", "rb") as f:
            G = pickle.load(f)
        stats["enriched_nodes"] = G.number_of_nodes()
        stats["enriched_edges"] = G.number_of_edges()
    if save:
        paths.enriched.mkdir(parents=True, exist_ok=True)
        with open(paths.enriched / "dataset_statistics.txt", "w") as f:
            for k, v in sorted(stats.items()):
                f.write(f"{k}: {v}\n")
    return stats
