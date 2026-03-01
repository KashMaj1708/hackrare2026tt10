"""
Phase 7: Train/validation/test splits (disease-centric) and back-test holdout.
CF, PAH, and DMD must be entirely in the test set (no edges from these diseases in train).
"""
import pickle
from pathlib import Path
import pandas as pd
import networkx as nx
from sklearn.model_selection import GroupShuffleSplit

from .config import get_paths

BACKTEST_DISEASES = {"Cystic fibrosis", "Pulmonary arterial hypertension", "Duchenne muscular dystrophy"}

# Also match lowercase / partial names for robustness
BACKTEST_PATTERNS = ["cystic fibrosis", "pulmonary arterial hypertension", "duchenne muscular dystrophy"]


def _resolve_backtest_disease_indices(paths) -> set:
    """Find node indices for CF, PAH, DMD from the enriched graph or disease_nodes."""
    backtest_indices = set()
    # Try enriched graph first
    gpickle = paths.enriched / "enriched_graph.gpickle"
    if gpickle.exists():
        try:
            with open(gpickle, "rb") as f:
                G = pickle.load(f)
            for n, d in G.nodes(data=True):
                name = str(d.get("name", "")).lower()
                if any(pat in name for pat in BACKTEST_PATTERNS):
                    backtest_indices.add(n)
        except Exception:
            pass
    # Fallback: disease_nodes.csv
    if not backtest_indices:
        dn_path = paths.processed / "disease_nodes.csv"
        if dn_path.exists():
            dn = pd.read_csv(dn_path)
            for _, row in dn.iterrows():
                name = str(row.get("node_name", "")).lower()
                if any(pat in name for pat in BACKTEST_PATTERNS):
                    backtest_indices.add(row["node_index"])
    return backtest_indices


def run_phase7(save: bool = True) -> tuple:
    paths = get_paths()
    pos_path = paths.enriched / "candidates_positives.csv"
    neg_path = paths.enriched / "candidates_negatives_hard.csv"
    if not pos_path.exists():
        raise FileNotFoundError("Run phase6 first to create candidates_positives.csv")
    pos = pd.read_csv(pos_path)
    neg = pd.read_csv(neg_path) if neg_path.exists() else pd.DataFrame(columns=["drug_index", "disease_index"])
    all_edges = pd.concat([pos.assign(label=1), neg.assign(label=0)], ignore_index=True)

    # Force CF/PAH/DMD entirely into test
    backtest_idx = _resolve_backtest_disease_indices(paths)
    backtest_mask = all_edges["disease_index"].isin(backtest_idx)
    backtest_edges = all_edges[backtest_mask].copy()
    remaining = all_edges[~backtest_mask].copy()

    if len(remaining) == 0:
        # All edges are backtest diseases
        train_final = pd.DataFrame(columns=all_edges.columns)
        val_df = pd.DataFrame(columns=all_edges.columns)
        test_df = all_edges.copy()
    else:
        # Disease-centric GroupShuffleSplit on remaining edges
        disease_groups = remaining["disease_index"].values
        splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
        train_idx, test_idx = next(splitter.split(remaining, groups=disease_groups))
        train_df = remaining.iloc[train_idx]
        test_df = pd.concat([remaining.iloc[test_idx], backtest_edges], ignore_index=True)
        # Val split from train
        if len(train_df) > 1:
            splitter2 = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=43)
            tr_idx, val_idx = next(splitter2.split(train_df, groups=train_df["disease_index"]))
            train_final = train_df.iloc[tr_idx]
            val_df = train_df.iloc[val_idx]
        else:
            train_final = train_df
            val_df = pd.DataFrame(columns=all_edges.columns)

    # Verify: no backtest diseases leaked into train or val
    if backtest_idx:
        train_leak = set(train_final["disease_index"]) & backtest_idx
        val_leak = set(val_df["disease_index"]) & backtest_idx
        if train_leak or val_leak:
            print(f"  WARNING: backtest disease leak — train: {train_leak}, val: {val_leak}")

    if save:
        paths.splits.mkdir(parents=True, exist_ok=True)
        train_final.to_csv(paths.splits / "train.csv", index=False)
        val_df.to_csv(paths.splits / "val.csv", index=False)
        test_df.to_csv(paths.splits / "test.csv", index=False)

    bt_in_test = set(test_df["disease_index"]) & backtest_idx if backtest_idx else set()
    print(f"  Back-test diseases in test set: {len(bt_in_test)} disease indices")

    return train_final, val_df, test_df
