"""
Phase 6: Merge all layers into enriched graph.
Build NetworkX graph with node/edge attributes, generate candidate drug-disease pairs.
"""
from pathlib import Path
import pandas as pd
import networkx as nx

from .config import get_paths
from .phase1_primekg import DRUG_DISEASE_RELATIONS, get_drug_disease_edges, get_disease_nodes, get_drug_nodes


def load_processed_tables(paths):
    """Load all processed CSVs needed for merge."""
    out = {}
    for name, key in [
        ("primekg_full.csv", "kg"),
        ("drug_disease_edges.csv", "drug_disease"),
        ("disease_nodes.csv", "disease_nodes"),
        ("drug_nodes.csv", "drug_nodes"),
        ("disease_rare_mask.csv", "rare_mask_df"),
        ("disease_orphanet_map.csv", "orphanet_map_df"),
        ("disease_hpo_annotations.csv", "hpo_df"),
        ("gene_mechanism.csv", "gene_mechanism"),
        ("drug_target_actions.csv", "drug_actions"),
        ("drug_safety.csv", "drug_safety"),
    ]:
        p = paths.processed / name
        if p.exists():
            out[key] = pd.read_csv(p)
        else:
            out[key] = None
    return out


def build_enriched_graph(tables: dict, kg: pd.DataFrame) -> nx.MultiDiGraph:
    """Build NetworkX MultiDiGraph with enriched node/edge attributes."""
    G = nx.MultiDiGraph()
    # Nodes: from kg unique (x_index,x_type) and (y_index,y_type)
    node_rows = []
    for _, row in kg.iterrows():
        node_rows.append({"index": row["x_index"], "id": row["x_id"], "type": row["x_type"], "name": row["x_name"]})
        node_rows.append({"index": row["y_index"], "id": row["y_id"], "type": row["y_type"], "name": row["y_name"]})
    nodes_df = pd.DataFrame(node_rows).drop_duplicates(subset=["index"])
    for _, row in nodes_df.iterrows():
        attrs = {"type": row["type"], "name": row["name"], "id": row["id"]}
        if tables.get("rare_mask_df") is not None:
            rm = tables["rare_mask_df"]
            match = rm[rm["node_id"].astype(str) == str(row["id"])]
            if not match.empty:
                attrs["is_rare"] = match.iloc[0].get("is_rare", False)
        if tables.get("orphanet_map_df") is not None:
            om = tables["orphanet_map_df"]
            match = om[om["node_id"].astype(str) == str(row["id"])]
            if not match.empty:
                attrs["orphanet_id"] = match.iloc[0].get("orphanet_id")
        if tables.get("hpo_df") is not None:
            hp = tables["hpo_df"]
            match = hp[hp["node_id"].astype(str) == str(row["id"])]
            if not match.empty:
                attrs["hpo_annotations"] = list(match[["hpo_id", "frequency"]].itertuples(index=False, name=None))
        G.add_node(row["index"], **attrs)
    # Edges
    for _, row in kg.iterrows():
        rel = row.get("relation") or row.get("display_relation")
        attrs = {"relation": rel}
        if row["x_type"] == "gene/protein" or row["y_type"] == "gene/protein":
            gene_id = row["y_id"] if row["y_type"] == "gene/protein" else row["x_id"]
            if tables.get("gene_mechanism") is not None:
                gm = tables["gene_mechanism"]
                m = gm[gm["gene_id"].astype(str) == str(gene_id)]
                if not m.empty:
                    attrs["mechanism"] = m.iloc[0].get("mechanism")
                    attrs["mechanism_confidence"] = m.iloc[0].get("mechanism_confidence")
        if "drug" in str(row["x_type"]).lower() and "gene" in str(row["y_type"]).lower():
            drug_id = row["x_id"]
            gene_id = row["y_id"]
            gene_symbol = str(gene_id)
            if tables.get("gene_mechanism") is not None:
                gm = tables["gene_mechanism"]
                m = gm[gm["gene_id"].astype(str) == str(gene_id)]
                if not m.empty and m.iloc[0].get("gene_symbol"):
                    gene_symbol = str(m.iloc[0]["gene_symbol"])
            if tables.get("drug_actions") is not None:
                da = tables["drug_actions"]
                m = da[(da["drugbank_id"].astype(str) == str(drug_id)) & (da["gene_symbol"].astype(str) == gene_symbol)]
                if not m.empty and m.iloc[0].get("actions"):
                    acts = m.iloc[0]["actions"]
                    if isinstance(acts, str):
                        acts = [a.strip() for a in acts.strip("[]").replace("'", "").split(",")]
                    attrs["drug_action"] = acts[0] if acts else "unknown"
        G.add_edge(row["x_index"], row["y_index"], **attrs)
    return G


def get_candidate_pairs(G: nx.MultiDiGraph) -> tuple:
    """Positive (indication), hard negative (contraindication), and rare disease list."""
    rare = [n for n, d in G.nodes(data=True) if d.get("is_rare") is True]
    drugs = [n for n, d in G.nodes(data=True) if "drug" in str(d.get("type", "")).lower()]
    positives = []
    negatives_hard = []
    for u, v, data in G.edges(data=True):
        rel = data.get("relation")
        if v not in rare and u not in rare:
            continue
        dis = v if v in rare else u
        dr = u if u in drugs else v
        if dr not in drugs:
            continue
        if rel == "indication":
            positives.append((dr, dis))
        elif rel == "contraindication":
            negatives_hard.append((dr, dis))
    return positives, negatives_hard, rare, drugs


def run_phase6(save: bool = True) -> nx.MultiDiGraph:
    """Load PrimeKG + processed tables, build enriched graph, save candidates. Returns G."""
    paths = get_paths()
    if not (paths.processed / "primekg_full.csv").exists():
        raise FileNotFoundError("Run phase1 first.")
    kg = pd.read_csv(paths.processed / "primekg_full.csv")
    tables = load_processed_tables(paths)
    G = build_enriched_graph(tables, kg)
    positives, negatives_hard, rare, drugs = get_candidate_pairs(G)
    if save:
        paths.enriched.mkdir(parents=True, exist_ok=True)
        nx.write_gpickle(G, paths.enriched / "enriched_graph.gpickle")
        pd.DataFrame(positives, columns=["drug_index", "disease_index"]).to_csv(
            paths.enriched / "candidates_positives.csv", index=False)
        pd.DataFrame(negatives_hard, columns=["drug_index", "disease_index"]).to_csv(
            paths.enriched / "candidates_negatives_hard.csv", index=False)
    return G
