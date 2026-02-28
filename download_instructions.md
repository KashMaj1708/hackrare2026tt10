# Data download instructions

Place files under `data/raw/<subdir>/` as below. After that, run:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python assemble_dataset.py
```

## Required for Phase 1 (minimum to run pipeline)

| Dataset | Source | Where to put | Key file |
|---------|--------|--------------|----------|
| **PrimeKG** | [Harvard Dataverse](https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/IXA7BM) | `data/raw/primekg/` | `kg.csv` or `edges.csv` |

## Optional (enables full enrichment)

| Dataset | Source | Where to put |
|---------|--------|--------------|
| **Orphanet/Orphadata** | [orphadata.com](https://www.orphadata.com/) (CC BY 4.0) | `data/raw/orphanet/` — XMLs: cross-referencing, HPO (e.g. `en_product6_prev.xml`, `en_product6_prev_HPO.xml`) |
| **MONDO** | [mondo.obo](https://github.com/monarch-initiative/mondo/releases) | `data/raw/mondo/mondo.obo` |
| **gnomAD constraint** | [gnomad.broadinstitute.org/downloads](https://gnomad.broadinstitute.org/downloads) | `data/raw/gnomad/` — e.g. `gnomad.v4.0.constraint_metrics.tsv` |
| **HGNC** | [genenames.org](https://www.genenames.org/download/statistics-and-files/) | `data/raw/hgnc/` — TSV with symbol + NCBI Gene ID |
| **ClinVar** | [ftp.ncbi.nlm.nih.gov/pub/clinvar/](https://ftp.ncbi.nlm.nih.gov/pub/clinvar/) | `data/raw/clinvar/` — `variant_summary.txt.gz` |
| **DrugBank** | [go.drugbank.com](https://go.drugbank.com/) (academic license) | `data/raw/drugbank/` — `full_database.xml` |
| **SIDER** | [sideeffects.embl.de](https://sideeffects.embl.de/) | `data/raw/sider/` — `meddra_all_se.tsv.gz` etc. |

If a raw folder is empty, that phase is skipped with a clear message.
