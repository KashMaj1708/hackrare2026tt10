# Evidence-traceable repurposing dataset

Dataset assembly pipeline for the **Evidence-Traceable Repurposing Shortlist** (PrimeKG + Orphanet, ClinVar/gnomAD, DrugBank/SIDER, evidence provenance).

## Setup (new Python env)

```powershell
cd c:\Users\kashy\Desktop\hackrare
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Data

- **Minimum:** Put PrimeKG in `data/raw/primekg/` as `kg.csv` or `edges.csv` (see [download_instructions.md](download_instructions.md)).
- A tiny **sample** `data/raw/primekg/kg_sample.csv` is included so you can run the pipeline; replace with full PrimeKG for real use.

## Run pipeline

```powershell
.\.venv\Scripts\Activate.ps1
python assemble_dataset.py
```

- `python assemble_dataset.py --phase 1` — run only phase 1 (PrimeKG load).
- `python assemble_dataset.py --through 6` — run phases 0 through 6 (stops before splits/stats).

Phases that need extra raw data (Orphanet, DrugBank, gnomAD, etc.) are skipped with a clear message if files are missing.

## Outputs

| Phase | Output |
|-------|--------|
| 1 | `data/processed/primekg_full.csv`, `drug_disease_edges.csv`, `disease_nodes.csv`, `drug_nodes.csv` |
| 2 | `disease_rare_mask.csv`, `disease_orphanet_map.csv`, `disease_hpo_annotations.csv` |
| 3 | `gene_mechanism.csv` |
| 4 | `drug_target_actions.csv`, `drug_safety.csv` |
| 5 | `primekg_with_evidence.csv` |
| 6 | `data/enriched/enriched_graph.gpickle`, `candidates_positives.csv`, `candidates_negatives_hard.csv` |
| 7 | `data/splits/train.csv`, `val.csv`, `test.csv` |
| 8 | `data/enriched/dataset_statistics.txt` |

## Layout

```
project/
├── data/raw/          # Downloaded files (primekg, orphanet, clinvar, gnomad, drugbank, sider, hgnc, mondo)
├── data/processed/    # Cleaned tables
├── data/enriched/     # Merged graph and candidates
├── data/splits/       # Train/val/test
├── configs/paths.yaml
├── src/data_pipeline/ # Phase modules
├── assemble_dataset.py
├── requirements.txt
└── download_instructions.md
```
