"""
Phase 3: Layer 2 — Mechanism annotation (LoF/GoF/DN).
gnomAD constraint, ClinVar + NLP variant labels, gene-level consensus.
"""
import re
from pathlib import Path
from collections import Counter
import pandas as pd

from .config import get_paths

# Plan 3.2.2
LOF_PATTERNS = [
    r"loss[\s-]of[\s-]function",
    r"\bLoF\b",
    r"haploinsufficiency",
    r"haploinsufficient",
    r"null\s+allele",
    r"truncating",
    r"loss\s+of\s+expression",
    r"reduced\s+expression",
]
GOF_PATTERNS = [
    r"gain[\s-]of[\s-]function",
    r"\bGoF\b",
    r"constitutively\s+activ",
    r"neomorphic",
    r"hypermorphic",
    r"oncogenic\s+mutation",
]
DN_PATTERNS = [
    r"dominant[\s-]negative",
    r"\bDN\b(?=\s+mutation|\s+variant|\s+effect)",
    r"antimorphic",
    r"poison\s+subunit",
]

LOF_CONSEQUENCES = {
    "frameshift_variant",
    "stop_gained",
    "splice_donor_variant",
    "splice_acceptor_variant",
    "start_lost",
    "transcript_ablation",
}


def label_variant_from_abstracts(abstracts: list) -> str:
    """Label variant as LoF/GoF/DN/conflicting/unknown from list of abstract strings."""
    text = " ".join((a or "") for a in abstracts).lower()
    lof = any(re.search(p, text, re.I) for p in LOF_PATTERNS)
    gof = any(re.search(p, text, re.I) for p in GOF_PATTERNS)
    dn = any(re.search(p, text, re.I) for p in DN_PATTERNS)
    if lof and not gof and not dn:
        return "LoF"
    if gof and not lof and not dn:
        return "GoF"
    if dn:
        return "DN"
    if lof and gof:
        return "conflicting"
    return "unknown"


def load_gnomad_constraint(paths) -> pd.DataFrame:
    """Load gnomAD constraint TSV; add lof_constrained, mis_constrained."""
    for name in ("gnomad.v4.0.constraint_metrics.tsv", "constraint_metrics.tsv", "gnomad*.tsv"):
        for p in paths.raw_gnomad.glob(name):
            try:
                df = pd.read_csv(p, sep="\t")
                if "gene" not in df.columns and "gene_symbol" in df.columns:
                    df = df.rename(columns={"gene_symbol": "gene"})
                if "oe_lof_upper" in df.columns:
                    df["lof_constrained"] = df["oe_lof_upper"] < 0.6
                elif "loeuf" in df.columns.str.lower():
                    col = [c for c in df.columns if "loeuf" in c.lower()][0]
                    df["lof_constrained"] = df[col] < 0.6
                else:
                    df["lof_constrained"] = False
                if "mis_z" in df.columns:
                    df["mis_constrained"] = df["mis_z"] > 3.09
                else:
                    df["mis_constrained"] = False
                return df
            except Exception:
                continue
    return pd.DataFrame()


def load_hgnc_mapping(paths) -> pd.DataFrame:
    """HGNC symbol <-> NCBI Gene ID. Columns: symbol, ncbi_gene_id (or equivalent)."""
    for p in list(paths.raw_hgnc.glob("*.tsv")) + list(paths.raw_hgnc.glob("*.txt")):
        try:
            df = pd.read_csv(p, sep="\t", low_memory=False)
            cols = {c.lower(): c for c in df.columns}
            if "symbol" in cols and ("ncbi" in str(cols) or "entrez" in str(cols).lower()):
                return df
        except Exception:
            continue
    return pd.DataFrame()


def assign_gene_mechanism(variant_labels: list, gnomad_row: dict, omim_inheritance: str = None):
    """Consensus gene-level mechanism and confidence. Plan 3.3."""
    evidence = {}
    label_counts = Counter(variant_labels)
    total_labeled = sum(v for k, v in label_counts.items() if k != "unknown")

    if total_labeled >= 1:
        for lab in ("LoF", "GoF", "DN"):
            if label_counts.get(lab, 0) / max(total_labeled, 1) >= 0.7:
                evidence["nlp_consensus"] = (lab, label_counts[lab] / total_labeled, total_labeled)
                break
        if "nlp_consensus" not in evidence and total_labeled >= 1:
            majority = max(["LoF", "GoF", "DN"], key=lambda x: label_counts.get(x, 0))
            evidence["nlp_consensus"] = (majority, label_counts.get(majority, 0) / total_labeled, total_labeled)

    if gnomad_row:
        try:
            oe = gnomad_row.get("oe_lof_upper", 1) if hasattr(gnomad_row, "get") else getattr(gnomad_row, "oe_lof_upper", 1)
            mz = gnomad_row.get("mis_z", 0) if hasattr(gnomad_row, "get") else getattr(gnomad_row, "mis_z", 0)
        except Exception:
            oe, mz = 1, 0
        if gnomad_row.get("lof_constrained", False) if hasattr(gnomad_row, "get") else getattr(gnomad_row, "lof_constrained", False):
            evidence["gnomad_lof_constrained"] = True
        elif (oe if oe == oe else 1) < 0.6:  # NaN check
            evidence["gnomad_lof_constrained"] = True
        if gnomad_row.get("mis_constrained", False) if hasattr(gnomad_row, "get") else getattr(gnomad_row, "mis_constrained", False):
            evidence["gnomad_mis_constrained"] = True
        elif (mz if mz == mz else 0) > 3.09:
            evidence["gnomad_mis_constrained"] = True

    if omim_inheritance == "AD":
        evidence["inheritance"] = "AD"

    if "nlp_consensus" in evidence:
        mechanism = evidence["nlp_consensus"][0]
        confidence = evidence["nlp_consensus"][1] * 0.7
        if mechanism == "LoF" and evidence.get("gnomad_lof_constrained"):
            confidence += 0.2
        elif mechanism == "GoF" and evidence.get("gnomad_mis_constrained"):
            confidence += 0.2
        confidence = min(confidence, 0.95)
    elif evidence.get("gnomad_lof_constrained") and not evidence.get("gnomad_mis_constrained"):
        mechanism = "LoF"
        confidence = 0.4
    elif evidence.get("gnomad_mis_constrained") and not evidence.get("gnomad_lof_constrained"):
        mechanism = "GoF"
        confidence = 0.3
    else:
        mechanism = "unknown"
        confidence = 0.0

    return mechanism, min(confidence, 1.0), evidence


def run_phase3(save: bool = True) -> pd.DataFrame:
    """Build gene-level mechanism table. Requires gnomAD (and optionally ClinVar + HGNC). Returns mechanism DataFrame."""
    paths = get_paths()
    gnomad = load_gnomad_constraint(paths)
    hgnc = load_hgnc_mapping(paths)

    if gnomad.empty:
        # Return empty schema so downstream doesn't break
        return pd.DataFrame(columns=["gene_id", "gene_symbol", "mechanism", "mechanism_confidence", "evidence"])

    # Map gene symbol -> NCBI id if we have HGNC
    symbol_to_ncbi = {}
    if not hgnc.empty:
        sc = "symbol" if "symbol" in hgnc.columns else hgnc.columns[0]
        ncbi_col = None
        for c in hgnc.columns:
            if "ncbi" in c.lower() or "entrez" in c.lower():
                ncbi_col = c
                break
        if ncbi_col:
            for _, r in hgnc.iterrows():
                sid = r.get(sc)
                nid = r.get(ncbi_col)
                if pd.notna(sid) and pd.notna(nid):
                    symbol_to_ncbi[str(sid).strip()] = str(int(nid)) if nid == nid else str(nid)

    gene_col = "gene" if "gene" in gnomad.columns else gnomad.columns[0]
    rows = []
    for _, row in gnomad.iterrows():
        sym = row.get(gene_col)
        if pd.isna(sym):
            continue
        sym = str(sym).strip()
        gene_id = symbol_to_ncbi.get(sym) or sym
        mechanism, confidence, evidence = assign_gene_mechanism(
            [],  # variant_labels: would come from ClinVar+NLP
            dict(row) if hasattr(row, "keys") else row,
            None,
        )
        rows.append({
            "gene_id": gene_id,
            "gene_symbol": sym,
            "mechanism": mechanism,
            "mechanism_confidence": confidence,
            "pLI": row.get("pLI"),
            "oe_lof_upper": row.get("oe_lof_upper"),
            "mis_z": row.get("mis_z"),
        })

    out = pd.DataFrame(rows)
    if save:
        paths.processed.mkdir(parents=True, exist_ok=True)
        out.to_csv(paths.processed / "gene_mechanism.csv", index=False)
    return out
