"""
Phase 6: Merge all layers into enriched graph.
Build NetworkX graph with node/edge attributes, generate candidate drug-disease pairs.
"""
import pickle
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
        if p.exists() and p.stat().st_size > 10:
            try:
                out[key] = pd.read_csv(p)
            except Exception:
                out[key] = None
        else:
            out[key] = None
    return out


def build_enriched_graph(tables: dict, kg: pd.DataFrame) -> nx.MultiDiGraph:
    """Build NetworkX MultiDiGraph with enriched node/edge attributes. Optimized with lookup dicts."""
    G = nx.MultiDiGraph()
    print("  Phase 6: building node table...")

    # --- Build unique nodes via vectorized concat ---
    x_nodes = kg[["x_index", "x_id", "x_type", "x_name"]].copy()
    x_nodes.columns = ["index", "id", "type", "name"]
    y_nodes = kg[["y_index", "y_id", "y_type", "y_name"]].copy()
    y_nodes.columns = ["index", "id", "type", "name"]
    nodes_df = pd.concat([x_nodes, y_nodes], ignore_index=True).drop_duplicates(subset=["index"])

    # --- Pre-build lookup dicts from enrichment tables (avoid per-row DF filtering) ---
    rare_lookup = {}
    if tables.get("rare_mask_df") is not None:
        rm = tables["rare_mask_df"]
        rare_lookup = dict(zip(rm["node_id"].astype(str), rm["is_rare"]))

    orphanet_lookup = {}
    if tables.get("orphanet_map_df") is not None:
        om = tables["orphanet_map_df"]
        orphanet_lookup = dict(zip(om["node_id"].astype(str), om["orphanet_id"]))

    hpo_lookup = {}
    if tables.get("hpo_df") is not None:
        hp = tables["hpo_df"]
        for nid, grp in hp.groupby(hp["node_id"].astype(str)):
            hpo_lookup[nid] = list(grp[["hpo_id", "frequency"]].itertuples(index=False, name=None))

    gene_mech_lookup = {}
    if tables.get("gene_mechanism") is not None:
        gm = tables["gene_mechanism"]
        for _, r in gm.iterrows():
            gid = str(r.get("gene_id", ""))
            gene_mech_lookup[gid] = {
                "mechanism": r.get("mechanism"),
                "mechanism_confidence": r.get("mechanism_confidence"),
                "gene_symbol": str(r.get("gene_symbol", "")),
            }

    drug_action_lookup = {}
    if tables.get("drug_actions") is not None:
        da = tables["drug_actions"]
        for _, r in da.iterrows():
            key = (str(r.get("drugbank_id", "")), str(r.get("gene_symbol", "")))
            acts = r.get("actions", "unknown")
            if isinstance(acts, str):
                acts = [a.strip() for a in acts.strip("[]").replace("'", "").split(",") if a.strip()]
            drug_action_lookup[key] = acts[0] if acts else "unknown"

    # --- Add nodes ---
    print(f"  Phase 6: adding {len(nodes_df)} nodes...")
    for row in nodes_df.itertuples(index=False):
        nid = str(row.id)
        attrs = {"type": row.type, "name": row.name, "id": row.id}
        if nid in rare_lookup:
            attrs["is_rare"] = rare_lookup[nid]
        if nid in orphanet_lookup:
            attrs["orphanet_id"] = orphanet_lookup[nid]
        if nid in hpo_lookup:
            attrs["hpo_annotations"] = hpo_lookup[nid]
        G.add_node(getattr(row, "index"), **attrs)

    # --- Add edges ---
    print(f"  Phase 6: adding {len(kg)} edges...")
    rel_col = "relation" if "relation" in kg.columns else "display_relation"
    x_types = kg["x_type"].astype(str).values
    y_types = kg["y_type"].astype(str).values
    relations = kg[rel_col].values if rel_col in kg.columns else [None] * len(kg)
    x_indices = kg["x_index"].values
    y_indices = kg["y_index"].values
    x_ids = kg["x_id"].astype(str).values
    y_ids = kg["y_id"].astype(str).values

    for i in range(len(kg)):
        rel = relations[i]
        attrs = {"relation": rel}
        xt = x_types[i]
        yt = y_types[i]
        # Mechanism enrichment for gene/protein edges
        if xt == "gene/protein" or yt == "gene/protein":
            gene_id = y_ids[i] if yt == "gene/protein" else x_ids[i]
            if gene_id in gene_mech_lookup:
                m = gene_mech_lookup[gene_id]
                attrs["mechanism"] = m["mechanism"]
                attrs["mechanism_confidence"] = m["mechanism_confidence"]
        # Drug action enrichment for drug->gene edges
        if "drug" in xt.lower() and "gene" in yt.lower():
            drug_id = x_ids[i]
            gene_id = y_ids[i]
            gene_symbol = gene_mech_lookup.get(gene_id, {}).get("gene_symbol", gene_id)
            action = drug_action_lookup.get((drug_id, gene_symbol))
            if action:
                attrs["drug_action"] = action
        G.add_edge(x_indices[i], y_indices[i], **attrs)
    return G


def get_candidate_pairs(G: nx.MultiDiGraph) -> tuple:
    """Positive (indication), hard negative (contraindication), and rare disease list.
    Falls back to ALL drug-disease edges when no rare diseases are tagged."""
    rare_set = {n for n, d in G.nodes(data=True) if d.get("is_rare") is True}
    drug_set = {n for n, d in G.nodes(data=True) if "drug" in str(d.get("type", "")).lower()}
    disease_set = {n for n, d in G.nodes(data=True) if "disease" in str(d.get("type", "")).lower()}

    # If no rare diseases found (missing Orphanet data), treat ALL diseases as candidates
    use_rare_filter = len(rare_set) > 0
    target_diseases = rare_set if use_rare_filter else disease_set
    if not use_rare_filter:
        print("  Phase 6: no rare-disease tags found — using all diseases as candidates")

    positives = []
    negatives_hard = []
    for u, v, data in G.edges(data=True):
        rel = data.get("relation")
        if rel not in ("indication", "contraindication", "off-label use"):
            continue
        # Determine drug and disease ends
        if u in drug_set and v in target_diseases:
            dr, dis = u, v
        elif v in drug_set and u in target_diseases:
            dr, dis = v, u
        else:
            continue
        if rel == "indication":
            positives.append((dr, dis))
        elif rel == "contraindication":
            negatives_hard.append((dr, dis))
    return positives, negatives_hard, list(target_diseases), list(drug_set)


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
        with open(paths.enriched / "enriched_graph.gpickle", "wb") as f:
            pickle.dump(G, f)
        pd.DataFrame(positives, columns=["drug_index", "disease_index"]).to_csv(
            paths.enriched / "candidates_positives.csv", index=False)
        pd.DataFrame(negatives_hard, columns=["drug_index", "disease_index"]).to_csv(
            paths.enriched / "candidates_negatives_hard.csv", index=False)
    return G
