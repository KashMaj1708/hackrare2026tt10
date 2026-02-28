"""
Phase 7: Train/validation/test splits (disease-centric) and back-test holdout.
"""
from pathlib import Path
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

from .config import get_paths

BACKTEST_DISEASES = {"Cystic fibrosis", "Pulmonary arterial hypertension", "Duchenne muscular dystrophy"}


def run_phase7(save: bool = True) -> tuple:
    paths = get_paths()
    pos_path = paths.enriched / "candidates_positives.csv"
    neg_path = paths.enriched / "candidates_negatives_hard.csv"
    if not pos_path.exists():
        raise FileNotFoundError("Run phase6 first to create candidates_positives.csv")
    pos = pd.read_csv(pos_path)
    neg = pd.read_csv(neg_path) if neg_path.exists() else pd.DataFrame(columns=["drug_index", "disease_index"])
    all_edges = pd.concat([pos.assign(label=1), neg.assign(label=0)], ignore_index=True)
    disease_groups = all_edges["disease_index"].values
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_idx, test_idx = next(splitter.split(all_edges, groups=disease_groups))
    train_df = all_edges.iloc[train_idx]
    test_df = all_edges.iloc[test_idx]
    splitter2 = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=43)
    tr_idx, val_idx = next(splitter2.split(train_df, groups=train_df["disease_index"]))
    train_final = train_df.iloc[tr_idx]
    val_df = train_df.iloc[val_idx]
    if save:
        paths.splits.mkdir(parents=True, exist_ok=True)
        train_final.to_csv(paths.splits / "train.csv", index=False)
        val_df.to_csv(paths.splits / "val.csv", index=False)
        test_df.to_csv(paths.splits / "test.csv", index=False)
    return train_final, val_df, test_df
