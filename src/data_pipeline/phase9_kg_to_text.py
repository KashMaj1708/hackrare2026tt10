"""
Phase 9 (was Phase 10 in plan): KG-to-Text conversion layer.
Converts enriched graph edges into (input, chain-of-thought, output) text triples
for LLM fine-tuning.  Generates:
  - Positive examples from indication edges
  - Hard negatives from contraindication edges
  - Random negatives (sampled)
  - Mechanism-flip synthetic hard negatives
"""
import json
import pickle
import random
from pathlib import Path
from collections import defaultdict

import pandas as pd
import networkx as nx

from .config import get_paths

random.seed(42)

# ---------------------------------------------------------------------------
# Subquestion templates
# ---------------------------------------------------------------------------

SQ1_TEMPLATE = (
    "SQ1 — Mechanism Compatibility\n"
    "Disease \"{disease}\" is associated with [{mechanism}] in gene [{gene}]. "
    "Drug \"{drug}\" is a [{action}] of [{gene}]. "
    "Is this mechanistically compatible?"
)

SQ2_TEMPLATE = (
    "SQ2 — Target/Pathway Overlap\n"
    "Drug \"{drug}\" targets: [{drug_targets}]. "
    "Disease \"{disease}\" pathway genes: [{disease_genes}]. "
    "Overlap: {overlap_count} shared targets, pathway Jaccard = {jaccard:.3f}."
)

SQ3_TEMPLATE = (
    "SQ3 — Safety Compatibility\n"
    "Patient constraints: pediatric={pediatric_safe}, avoid=[{avoid}]. "
    "Drug \"{drug}\" safety flags: [{safety_flags}]. Route: [{route}]. Compatible?"
)

SQ4_TEMPLATE = (
    "SQ4 — Human Evidence\n"
    "Evidence type for ({drug}, {disease}): [{evidence_type}]. "
    "Evidence score: {evidence_score:.2f}. Evidence tier: [{tier}]."
)

FINAL_TEMPLATE = (
    "Final Assessment:\n"
    "Repurposing candidate: {drug} -> {disease}\n"
    "Score: {score:.2f} | Verdict: {verdict}\n"
    "Evidence: {evidence_summary}\n"
    "Uncertainty: {uncertainty}"
)


def _safe_json_list(val):
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, ValueError):
            return [v.strip().strip("'\"") for v in val.strip("[]").split(",") if v.strip()]
    return []


def _tier_from_score(score: float) -> str:
    if score >= 0.75:
        return "strong"
    if score >= 0.5:
        return "moderate"
    if score >= 0.25:
        return "weak"
    return "minimal"


# ---------------------------------------------------------------------------
# Build text examples from enriched graph
# ---------------------------------------------------------------------------

def _gather_node_info(G, node_idx):
    """Collect drug or disease info from graph node attributes."""
    d = G.nodes.get(node_idx, {})
    return {
        "name": d.get("name", str(node_idx)),
        "type": d.get("type", ""),
        "id": d.get("id", ""),
        "is_rare": d.get("is_rare", False),
        "hpo_annotations": d.get("hpo_annotations", []),
    }


def _gather_drug_targets_from_graph(G, drug_idx) -> list:
    """Get gene targets for a drug from graph edges."""
    targets = []
    for _, v, data in G.edges(drug_idx, data=True):
        node_d = G.nodes.get(v, {})
        if "gene" in str(node_d.get("type", "")).lower():
            targets.append({
                "gene": node_d.get("name", str(v)),
                "action": data.get("drug_action", "unknown"),
                "mechanism": data.get("mechanism", "unknown"),
                "mechanism_confidence": data.get("mechanism_confidence", 0.0),
            })
    return targets


def _gather_disease_genes_from_graph(G, disease_idx) -> list:
    """Get genes associated with a disease from graph edges (O(degree), not O(E))."""
    genes = []
    seen = set()
    # Out-edges from disease
    for _, v, data in G.edges(disease_idx, data=True):
        if v not in seen:
            node_d = G.nodes.get(v, {})
            if "gene" in str(node_d.get("type", "")).lower():
                genes.append(node_d.get("name", str(v)))
                seen.add(v)
    # In-edges to disease (predecessors in DiGraph)
    for u in G.predecessors(disease_idx):
        if u not in seen:
            node_d = G.nodes.get(u, {})
            if "gene" in str(node_d.get("type", "")).lower():
                genes.append(node_d.get("name", str(u)))
                seen.add(u)
    return genes


def _get_edge_evidence(G, drug_idx, disease_idx, relation):
    """Extract evidence type and score from graph edges between drug and disease."""
    ev_type = "computational"
    ev_score = 0.25
    # Check direct edges between drug and disease
    if G.has_node(drug_idx) and G.has_node(disease_idx):
        for u, v, data in G.edges(drug_idx, data=True):
            if v == disease_idx:
                if data.get("evidence_type"):
                    ev_type = str(data["evidence_type"])
                if data.get("evidence_score"):
                    try:
                        ev_score = float(data["evidence_score"])
                    except (ValueError, TypeError):
                        pass
                break
        # Also check reverse direction
        if ev_type == "computational":
            for u, v, data in G.edges(disease_idx, data=True):
                if v == drug_idx:
                    if data.get("evidence_type"):
                        ev_type = str(data["evidence_type"])
                    if data.get("evidence_score"):
                        try:
                            ev_score = float(data["evidence_score"])
                        except (ValueError, TypeError):
                            pass
                    break
    return ev_type, ev_score


def _build_example(G, drug_idx, disease_idx, relation, drug_records_map):
    """Build one (input, chain_of_thought, output) triple."""
    drug_info = _gather_node_info(G, drug_idx)
    disease_info = _gather_node_info(G, disease_idx)
    drug_name = drug_info["name"]
    disease_name = disease_info["name"]

    drug_targets = _gather_drug_targets_from_graph(G, drug_idx)
    disease_genes = _gather_disease_genes_from_graph(G, disease_idx)

    drug_target_names = [t["gene"] for t in drug_targets]
    overlap = set(drug_target_names) & set(disease_genes)
    union = set(drug_target_names) | set(disease_genes)
    jaccard = len(overlap) / max(len(union), 1)

    # SQ1
    if drug_targets:
        t = drug_targets[0]
        sq1 = SQ1_TEMPLATE.format(
            disease=disease_name, mechanism=t.get("mechanism", "unknown"),
            gene=t["gene"], drug=drug_name, action=t.get("action", "unknown"))
    else:
        sq1 = f"SQ1 — Mechanism Compatibility\nNo known gene targets for drug \"{drug_name}\"."

    # SQ2
    sq2 = SQ2_TEMPLATE.format(
        drug=drug_name, drug_targets=", ".join(drug_target_names) or "none",
        disease=disease_name, disease_genes=", ".join(disease_genes[:10]) or "none",
        overlap_count=len(overlap), jaccard=jaccard)

    # SQ3 — use consolidated drug record if available
    drec = drug_records_map.get(str(drug_info["id"]), {})
    safety_flags = _safe_json_list(drec.get("safety_flags", []))
    routes = _safe_json_list(drec.get("routes", []))
    pediatric = drec.get("pediatric_safe", True)
    sq3 = SQ3_TEMPLATE.format(
        pediatric_safe=pediatric, avoid="none",
        drug=drug_name, safety_flags=", ".join(safety_flags) or "none",
        route=", ".join(routes) or "unknown")

    # SQ4 — evidence (from graph edges, not the massive CSV)
    ev_type, ev_score = _get_edge_evidence(G, drug_idx, disease_idx, relation)
    tier = _tier_from_score(ev_score)
    sq4 = SQ4_TEMPLATE.format(
        drug=drug_name, disease=disease_name,
        evidence_type=ev_type, evidence_score=ev_score, tier=tier)

    # Chain of thought
    cot = f"{sq1}\n\n{sq2}\n\n{sq3}\n\n{sq4}"

    # Score and verdict
    if relation == "indication":
        score = 0.5 + jaccard * 0.3 + ev_score * 0.2
        verdict = "CANDIDATE — positive indication"
        label = 1
    elif relation == "contraindication":
        score = 0.1 + jaccard * 0.1
        verdict = "REJECT — contraindicated"
        label = 0
    elif relation == "mechanism_flip":
        score = 0.15
        verdict = "REJECT — mechanism incompatible"
        label = 0
    else:
        score = 0.2 + jaccard * 0.2 + ev_score * 0.1
        verdict = "UNLIKELY — random negative"
        label = 0

    moa_text = str(drec.get("moa", "") or "")
    moa_text = "" if moa_text == "nan" else moa_text
    desc_text = str(drec.get("description", "") or "")
    desc_text = "" if desc_text == "nan" else desc_text

    input_text = (
        f"Evaluate drug repurposing candidate:\n"
        f"Drug: {drug_name}"
        + (f"\nMOA: {moa_text}" if moa_text else "")
        + (f"\nDescription: {desc_text[:200]}" if desc_text else "")
        + f"\nDisease: {disease_name} (rare={disease_info['is_rare']})"
    )

    uncertainty = "Low" if ev_score >= 0.5 and len(drug_targets) > 0 else "Moderate" if ev_score >= 0.25 else "High"
    output_text = FINAL_TEMPLATE.format(
        drug=drug_name, disease=disease_name, score=min(score, 1.0),
        verdict=verdict,
        evidence_summary=f"{ev_type} (score={ev_score:.2f}), {len(overlap)} shared targets",
        uncertainty=uncertainty)

    return {
        "input": input_text,
        "chain_of_thought": cot,
        "output": output_text,
        "label": label,
        "relation": relation,
        "drug_index": drug_idx,
        "disease_index": disease_idx,
        "drug_name": drug_name,
        "disease_name": disease_name,
        "score": min(score, 1.0),
    }


# ---------------------------------------------------------------------------
# Mechanism-flip synthetic negatives
# ---------------------------------------------------------------------------

ACTION_OPPOSITES = {
    "inhibitor": "agonist",
    "agonist": "inhibitor",
    "antagonist": "agonist",
    "activator": "inhibitor",
    "blocker": "activator",
    "inducer": "inhibitor",
    "suppressor": "activator",
}


def _generate_mechanism_flips(G, positives, drug_nodes, max_flips=3000):
    """For each positive (drug, disease), find a drug with the opposite action on same target."""
    # Build drug->gene->action index
    drug_gene_action = defaultdict(dict)
    for d_idx in drug_nodes:
        for _, v, data in G.edges(d_idx, data=True):
            node_d = G.nodes.get(v, {})
            if "gene" in str(node_d.get("type", "")).lower():
                gene_name = node_d.get("name", str(v))
                action = data.get("drug_action", "unknown")
                drug_gene_action[d_idx][gene_name] = action

    # For each positive, try to find a drug targeting same gene with opposite action
    flips = []
    for drug_idx, disease_idx in positives:
        if len(flips) >= max_flips:
            break
        drug_genes = drug_gene_action.get(drug_idx, {})
        for gene, action in drug_genes.items():
            opposite = ACTION_OPPOSITES.get(action.lower(), None)
            if not opposite:
                continue
            # Find another drug with opposite action on same gene
            for other_drug, other_genes in drug_gene_action.items():
                if other_drug == drug_idx:
                    continue
                if gene in other_genes and other_genes[gene].lower() == opposite:
                    flips.append((other_drug, disease_idx))
                    break
            if len(flips) >= max_flips:
                break
    return flips


def _generate_random_negatives(G, positives, negatives_hard, drug_nodes, rare_diseases, max_negatives=5000):
    """Sample random (drug, rare_disease) pairs that aren't known positives or hard negatives."""
    existing = set(positives) | set(negatives_hard)
    candidates = []
    attempts = 0
    while len(candidates) < max_negatives and attempts < max_negatives * 10:
        d = random.choice(drug_nodes)
        r = random.choice(rare_diseases)
        if (d, r) not in existing and (d, r) not in set(candidates):
            candidates.append((d, r))
        attempts += 1
    return candidates


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def run_phase9(save: bool = True) -> pd.DataFrame:
    """Convert enriched graph into text training examples. Returns DataFrame of examples."""
    paths = get_paths()

    # Load enriched graph
    gpickle = paths.enriched / "enriched_graph.gpickle"
    if not gpickle.exists():
        raise FileNotFoundError("Run phase6 first to create enriched_graph.gpickle")
    with open(gpickle, "rb") as f:
        G = pickle.load(f)

    # Load drug records
    drug_records_map = {}
    drec_path = paths.processed / "drug_records_consolidated.csv"
    if drec_path.exists():
        drec_df = pd.read_csv(drec_path)
        for _, row in drec_df.iterrows():
            drug_records_map[str(row.get("drugbank_id", ""))] = row.to_dict()

    # Identify nodes
    rare_diseases = [n for n, d in G.nodes(data=True) if d.get("is_rare") is True]
    drug_nodes = [n for n, d in G.nodes(data=True) if "drug" in str(d.get("type", "")).lower()]

    # Collect positive / hard negative pairs from candidates
    pos_path = paths.enriched / "candidates_positives.csv"
    neg_path = paths.enriched / "candidates_negatives_hard.csv"
    positives = []
    negatives_hard = []
    if pos_path.exists():
        pdf = pd.read_csv(pos_path)
        positives = list(zip(pdf["drug_index"], pdf["disease_index"]))
    if neg_path.exists():
        ndf = pd.read_csv(neg_path)
        negatives_hard = list(zip(ndf["drug_index"], ndf["disease_index"]))

    print(f"  Positives: {len(positives)}, Hard negatives: {len(negatives_hard)}")

    # Mechanism-flip synthetic negatives
    flips = _generate_mechanism_flips(G, positives, drug_nodes, max_flips=3000)
    print(f"  Mechanism-flip synthetics: {len(flips)}")

    # Random negatives
    if rare_diseases and drug_nodes:
        random_negs = _generate_random_negatives(G, positives, negatives_hard, drug_nodes, rare_diseases, max_negatives=5000)
    else:
        random_negs = []
    print(f"  Random negatives: {len(random_negs)}")

    # Build text examples
    examples = []
    for drug_idx, disease_idx in positives:
        ex = _build_example(G, drug_idx, disease_idx, "indication", drug_records_map)
        examples.append(ex)

    for drug_idx, disease_idx in negatives_hard:
        ex = _build_example(G, drug_idx, disease_idx, "contraindication", drug_records_map)
        examples.append(ex)

    for drug_idx, disease_idx in flips:
        ex = _build_example(G, drug_idx, disease_idx, "mechanism_flip", drug_records_map)
        examples.append(ex)

    for drug_idx, disease_idx in random_negs:
        ex = _build_example(G, drug_idx, disease_idx, "random_negative", drug_records_map)
        examples.append(ex)

    df = pd.DataFrame(examples) if examples else pd.DataFrame(columns=[
        "input", "chain_of_thought", "output", "label", "relation",
        "drug_index", "disease_index", "drug_name", "disease_name", "score"])

    print(f"  Total training examples: {len(df)}")

    if save:
        paths.enriched.mkdir(parents=True, exist_ok=True)
        df.to_csv(paths.enriched / "training_examples.csv", index=False)
        # Also save as JSONL for easier LLM consumption
        jsonl_path = paths.enriched / "training_examples.jsonl"
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for _, row in df.iterrows():
                f.write(json.dumps(row.to_dict(), default=str) + "\n")

    return df
