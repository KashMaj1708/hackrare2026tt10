#!/usr/bin/env python3
"""
Evidence-traceable repurposing dataset assembly.
Run from project root with: .venv\\Scripts\\activate then python assemble_dataset.py

Phases:
  0   - Ensure dirs and config                       (~1 s)
  1   - Load PrimeKG, extract drug-disease subgraph  (~2-5 min for full kg.csv)
  2   - Orphanet rare-disease filter + HPO            (~10-30 s)
  3   - Mechanism annotation + quality filter         (~5-20 s)
  4   - DrugBank safety/pharmacology                  (~1-5 min if XML present)
  4.5 - Consolidated drug records (moa, atc, SE)      (~30-90 s)
  5   - Evidence provenance on edges                  (~30-60 s)
  6   - Merge enriched graph, candidate pairs         (~2-5 min)
  7   - Disease-centric train/val/test splits         (~5-15 s)
  8   - Dataset statistics                            (~5-10 s)
  9   - KG-to-text conversion (LLM training data)     (~1-3 min)
"""
import sys
import time
import argparse
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data_pipeline.config import get_paths
from src.data_pipeline import phase1_primekg
from src.data_pipeline import phase2_orphanet
from src.data_pipeline import phase3_mechanism
from src.data_pipeline import phase4_safety
from src.data_pipeline import phase4_5_drug_records
from src.data_pipeline import phase5_evidence
from src.data_pipeline import phase6_merge
from src.data_pipeline import phase7_splits
from src.data_pipeline import phase8_stats
from src.data_pipeline import phase9_kg_to_text

# Ordered list of phases (using float keys for 4.5)
PHASE_ORDER = [1, 2, 3, 4, 4.5, 5, 6, 7, 8, 9]

PHASE_ESTIMATES = {
    0:   "~1 s",
    1:   "~2-5 min (full PrimeKG ~981 MB)",
    2:   "~10-30 s",
    3:   "~5-20 s",
    4:   "~1-5 min (DrugBank XML)",
    4.5: "~30-90 s",
    5:   "~30-60 s",
    6:   "~2-5 min",
    7:   "~5-15 s",
    8:   "~5-10 s",
    9:   "~1-3 min",
}


def phase0():
    paths = get_paths()
    for d in (paths.raw, paths.processed, paths.enriched, paths.splits,
              paths.raw_primekg, paths.raw_orphanet, paths.raw_clinvar,
              paths.raw_gnomad, paths.raw_drugbank, paths.raw_sider, paths.raw_hgnc, paths.raw_mondo):
        d.mkdir(parents=True, exist_ok=True)
    print("Phase 0: directories and config OK.")


def _fmt_elapsed(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    m, s = divmod(seconds, 60)
    return f"{int(m)}m {s:.1f}s"


def run_single_phase(phase_num, verbose=True):
    """Run a single phase by number. Returns a summary string."""
    est = PHASE_ESTIMATES.get(phase_num, "")
    if verbose:
        print(f"\n{'='*60}")
        print(f"Phase {phase_num}  (estimate: {est})")
        print(f"{'='*60}")

    t0 = time.time()

    if phase_num == 0:
        phase0()
        return "OK"
    elif phase_num == 1:
        kg, drug_disease, disease_nodes, drug_nodes = phase1_primekg.run_phase1(save_processed=True)
        msg = (f"PrimeKG loaded. Diseases: {len(disease_nodes)}, Drugs: {len(drug_nodes)}, "
               f"Drug-disease edges: {len(drug_disease)}")
    elif phase_num == 2:
        rare_mask, orphanet_map, hpo_map = phase2_orphanet.run_phase2(save=True)
        msg = (f"Rare mask: {sum(rare_mask.values())} rare diseases, "
               f"HPO annotations: {sum(len(v) for v in hpo_map.values())} total")
    elif phase_num == 3:
        gm = phase3_mechanism.run_phase3(save=True)
        msg = f"Gene mechanism: {len(gm)} genes with constraint/mechanism"
    elif phase_num == 4:
        da, ds = phase4_safety.run_phase4(save=True)
        msg = f"Drug targets: {len(da)}, Drug safety: {len(ds)}"
    elif phase_num == 4.5:
        dr = phase4_5_drug_records.run_phase4_5(save=True)
        msg = f"Consolidated drug records: {len(dr)}"
    elif phase_num == 5:
        kg_ev = phase5_evidence.run_phase5(kg=None, save=True)
        msg = f"Evidence added to {len(kg_ev)} edges"
    elif phase_num == 6:
        G = phase6_merge.run_phase6(save=True)
        msg = f"Enriched graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges"
    elif phase_num == 7:
        train, val, test = phase7_splits.run_phase7(save=True)
        msg = f"Train: {len(train)}, Val: {len(val)}, Test: {len(test)}"
    elif phase_num == 8:
        s = phase8_stats.run_phase8(save=True)
        msg = f"Statistics: {s}"
    elif phase_num == 9:
        df = phase9_kg_to_text.run_phase9(save=True)
        msg = f"Training examples: {len(df)} (saved CSV + JSONL)"
    else:
        msg = f"Unknown phase {phase_num}"

    elapsed = time.time() - t0
    summary = f"Phase {phase_num}: {msg}  [{_fmt_elapsed(elapsed)}]"
    if verbose:
        print(summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description="Assemble evidence-traceable repurposing dataset")
    parser.add_argument("--phase", type=float, default=None,
                        help="Run only this phase (0-9, use 4.5 for consolidated drug records)")
    parser.add_argument("--through", type=float, default=9,
                        help="Run phases 0 through N (default: all through 9)")
    parser.add_argument("--skip-downloads", action="store_true", help="Do not prompt about downloads")
    args = parser.parse_args()

    # Print time estimates
    print("\n  Phase time estimates:")
    for p in [0] + PHASE_ORDER:
        print(f"    Phase {p:>4}: {PHASE_ESTIMATES.get(p, '?')}")
    print()

    t_total = time.time()
    phase0()

    if args.phase is not None:
        if args.phase == 0:
            return
        phases_to_run = [args.phase]
    else:
        phases_to_run = [p for p in PHASE_ORDER if p <= args.through]

    summaries = []
    for phase_num in phases_to_run:
        try:
            s = run_single_phase(phase_num)
            summaries.append(s)
        except FileNotFoundError as e:
            msg = f"Phase {phase_num} skipped (missing data): {e}"
            print(msg)
            summaries.append(msg)
        except Exception as e:
            msg = f"Phase {phase_num} error: {e}"
            print(msg)
            summaries.append(msg)
            raise

    total_elapsed = time.time() - t_total
    print(f"\n{'='*60}")
    print(f"ALL PHASES COMPLETE  [total: {_fmt_elapsed(total_elapsed)}]")
    print(f"{'='*60}")
    for s in summaries:
        print(f"  {s}")
    print()


if __name__ == "__main__":
    main()
