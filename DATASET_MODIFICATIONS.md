# Dataset Modifications Required

Based on review of the original KG construction plan against LLM fine-tuning requirements.

---

## 1. Drug Data: Missing Consolidated Record (Phase 4.5)

The original plan scatters drug data across multiple phases but never consolidates it. Add a **Phase 4.5** step after DrugBank + SIDER parsing that produces one flat record per drug:

```python
drug_record = {
    "drugbank_id":        str,          # already in PrimeKG
    "name":               str,          # already in PrimeKG
    "drug_class":         str,          # ATC level-3 label  <- MISSING
    "atc_codes":          list[str],    # from DrugBank XML   <- MISSING
    "moa":                str,          # mechanism-of-action free text <- MISSING
    "description":        str,          # general description free text <- MISSING
    "targets": [{
        "gene":           str,
        "ncbi_id":        str,
        "action":         str,          # inhibitor / agonist / antagonist
        "known_action":   str,
    }],
    "safety_flags":       list[str],    # hepatotoxicity, QT prolongation, etc.
    "pediatric_safe":     bool,
    "pregnancy_category": str,
    "routes":             list[str],
    "top_side_effects":   list[tuple],  # (se_name, frequency) from SIDER <- MISSING
}
```

**Why it matters:** The LLM prompt needs natural language MOA text to reason over, not just raw action-type codes. `moa` and `description` fields from DrugBank XML are what make subquestion 1 (mechanism compatibility) actually work.

**Where to pull from DrugBank XML:**
```python
moa         = drug.find('db:mechanism-of-action', ns)
description = drug.find('db:description', ns)
atc_codes   = [a.text for a in drug.findall('.//db:atc-codes/db:atc-code', ns)]
```

---

## 2. Mechanism Label Quality Filter (Phase 3.3)

The NLP-derived LoF/GoF labels from ClinVar have ~70-75% precision. Training on noisy labels breaks the mechanism-compatibility subquestion. Add this filter before writing mechanism labels to any training example:

```python
# Only propagate mechanism labels that meet BOTH thresholds
if confidence >= 0.6 and total_labeled_variants >= 3:
    gene_mechanism[gene_id] = (mechanism, confidence)
else:
    gene_mechanism[gene_id] = ("unknown", 0.0)  # hedge, don't guess
```

Low-confidence labels should become `unknown` in training data, not noisy positives.

---

## 3. KG-to-Text Conversion Layer (Phase 10 — New Phase)

The original plan ends at graph export for GNN. For LLM fine-tuning you need an additional phase that converts enriched graph edges into `(input, chain-of-thought, output)` text triples.

**Subquestion template per candidate pair:**

```
SQ1 — Mechanism Compatibility
  "Disease Y is caused by [mechanism] in [gene]. Drug X is an [action] of [gene].
   Is this mechanistically compatible?"

SQ2 — Target/Pathway Overlap
  "Drug X targets: [genes]. Disease Y pathway genes: [genes].
   Overlap: [N] shared targets, pathway Jaccard = [score]."

SQ3 — Safety Compatibility
  "Patient constraints: pediatric=[bool], avoid=[categories].
   Drug X safety flags: [flags]. Route: [route]. Compatible?"

SQ4 — Human Evidence
  "Clinical trials for (Drug X, Disease Y): [N].
   Off-label precedent: [bool]. Evidence tier: [tier]."

Final Output:
  Ranked score, evidence ledger, uncertainty note.
```

**Training example sources and expected counts:**

| Source | Count |
|--------|-------|
| Positive indication edges (rare diseases) | ~1,500-2,500 |
| Contraindication hard negatives | ~800-1,200 |
| Random negatives (sampled) | ~5,000-8,000 |
| Mechanism-flip synthetic hard negatives | ~2,000-3,000 |
| Off-label weak positives | ~1,000-1,500 |
| **Total** | **~10K-16K** |

**Mechanism-flip synthetics** are the most informative negatives: take a correct (drug, disease) pair and swap the drug for one with the opposite action type on the same target. SQ1 should catch the incompatibility. These teach the model exactly what to look for.

---

## 4. Train/Val/Test Split — Confirm Disease-Centric

Verify your current split is disease-centric, not random edge splitting. If you used random splitting, redo it:

```python
from sklearn.model_selection import GroupShuffleSplit

disease_groups = [edge[1] for edge in all_edges]  # group by disease node
splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
train_idx, test_idx = next(splitter.split(all_edges, groups=disease_groups))
```

CF, PAH, and DMD must be entirely in the test set (no edges from these diseases in train).

---

## 5. What Does NOT Need Changing

- PrimeKG loading and edge type inventory
- Orphanet MONDO mapping chain (ORPHA -> ORDO -> MONDO, fallback via OMIM)
- HPO frequency annotation attachment
- gnomAD constraint score joins (pLI, LOEUF, mis_z)
- DrugBank action type extraction (inhibitor/agonist/antagonist)
- SIDER side effect mapping via STITCH -> PubChem -> DrugBank
- Evidence provenance hierarchy and ClinicalTrials.gov API enrichment
- Back-test validation diseases (CF + Ivacaftor, PAH + Sildenafil, DMD + Deflazacort)

---

## Summary Checklist

- [ ] Phase 4.5 added: flat drug record with `moa`, `description`, `atc_codes`, `top_side_effects`
- [ ] Mechanism label filter applied: confidence >= 0.6 AND >= 3 variants, else `unknown`
- [ ] Phase 10 added: KG-to-text conversion generating subquestion chain per candidate pair
- [ ] Mechanism-flip synthetic negatives generated (~2K-3K examples)
- [ ] Split confirmed as disease-centric (GroupShuffleSplit by disease node)
- [ ] CF / PAH / DMD confirmed absent from train set
