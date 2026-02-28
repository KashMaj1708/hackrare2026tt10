#!/usr/bin/env python3
"""
Evidence-traceable repurposing dataset assembly.
Run from project root with: .venv\\Scripts\\activate then python assemble_dataset.py

Phases:
  0 - Ensure dirs and config
  1 - Load PrimeKG, extract drug-disease subgraph
  2 - Orphanet rare-disease filter + HPO (requires raw Orphanet/MONDO)
  3 - Mechanism annotation from gnomAD (optional ClinVar+NLP)
  4 - DrugBank safety/pharmacology (requires DrugBank XML)
  5 - Evidence provenance on edges
  6 - Merge enriched graph, candidate pairs
  7 - Disease-centric train/val/test splits
  8 - Dataset statistics
"""
import sys
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
from src.data_pipeline import phase5_evidence
from src.data_pipeline import phase6_merge
from src.data_pipeline import phase7_splits
from src.data_pipeline import phase8_stats


def phase0():
    paths = get_paths()
    for d in (paths.raw, paths.processed, paths.enriched, paths.splits,
              paths.raw_primekg, paths.raw_orphanet, paths.raw_clinvar,
              paths.raw_gnomad, paths.raw_drugbank, paths.raw_sider, paths.raw_hgnc, paths.raw_mondo):
        d.mkdir(parents=True, exist_ok=True)
    print("Phase 0: directories and config OK.")


def main():
    parser = argparse.ArgumentParser(description="Assemble evidence-traceable repurposing dataset")
    parser.add_argument("--phase", type=int, default=None, help="Run only this phase (0-8)")
    parser.add_argument("--through", type=int, default=8, help="Run phases 0 through N")
    parser.add_argument("--skip-downloads", action="store_true", help="Do not prompt about downloads")
    args = parser.parse_args()

    phase0()
    if args.phase is not None:
        if args.phase == 0:
            return
        run_phase = args.phase
        through = args.phase
    else:
        run_phase = 1
        through = args.through

    for phase_num in range(run_phase, through + 1):
        try:
            if phase_num == 1:
                kg, drug_disease, disease_nodes, drug_nodes = phase1_primekg.run_phase1(save_processed=True)
                print(f"Phase 1: PrimeKG loaded. Diseases: {len(disease_nodes)}, Drugs: {len(drug_nodes)}, "
                      f"Drug-disease edges: {len(drug_disease)}")
            elif phase_num == 2:
                rare_mask, orphanet_map, hpo_map = phase2_orphanet.run_phase2(save=True)
                print(f"Phase 2: Rare mask: {sum(rare_mask.values())} rare diseases, "
                      f"HPO annotations: {sum(len(v) for v in hpo_map.values())} total")
            elif phase_num == 3:
                gm = phase3_mechanism.run_phase3(save=True)
                print(f"Phase 3: Gene mechanism: {len(gm)} genes with constraint/mechanism")
            elif phase_num == 4:
                da, ds = phase4_safety.run_phase4(save=True)
                print(f"Phase 4: Drug targets: {len(da)}, Drug safety: {len(ds)}")
            elif phase_num == 5:
                kg_ev = phase5_evidence.run_phase5(kg=None, save=True)
                print(f"Phase 5: Evidence added to {len(kg_ev)} edges")
            elif phase_num == 6:
                G = phase6_merge.run_phase6(save=True)
                print(f"Phase 6: Enriched graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
            elif phase_num == 7:
                train, val, test = phase7_splits.run_phase7(save=True)
                print(f"Phase 7: Train: {len(train)}, Val: {len(val)}, Test: {len(test)}")
            elif phase_num == 8:
                s = phase8_stats.run_phase8(save=True)
                print("Phase 8: Statistics:", s)
        except FileNotFoundError as e:
            print(f"Phase {phase_num} skipped (missing data): {e}")
        except Exception as e:
            print(f"Phase {phase_num} error: {e}")
            raise

    print("Done.")


if __name__ == "__main__":
    main()
