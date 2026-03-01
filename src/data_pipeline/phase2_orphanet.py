"""
Phase 2: Layer 1 — Rare-disease filter via Orphadata XML files.

Uses freely available Orphadata scientific knowledge files (CC BY 4.0):
  - en_product9_prev.xml  → epidemiology / rare-disease list
  - en_product1.xml       → alignments (OMIM, MONDO cross-refs)
  - en_product4.xml       → HPO phenotype annotations

Mapping strategy to PrimeKG:
  PrimeKG disease nodes use MONDO IDs as node_id.  Orphadata product1
  provides OrphaCode↔MONDO cross-references, so we build:
    orpha_to_mondo  →  tag PrimeKG nodes as is_rare
    orpha_to_hpo    →  attach HPO annotations
"""
from pathlib import Path
import xml.etree.ElementTree as ET
import pandas as pd

from .config import get_paths


# ---------------------------------------------------------------------------
# Parse Orphadata product9: epidemiology → set of rare OrphaCodes
# ---------------------------------------------------------------------------

def parse_product9_rare_diseases(xml_path: Path) -> dict:
    """Return {orpha_code: disease_name} for every disorder in the
    epidemiology file (all entries are rare diseases by definition)."""
    rare = {}
    if not xml_path.exists():
        return rare
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for disorder in root.findall(".//Disorder"):
            oc = disorder.find("OrphaCode")
            nm = disorder.find("Name")
            if oc is not None and oc.text:
                code = oc.text.strip()
                name = nm.text.strip() if nm is not None and nm.text else ""
                rare[code] = name
    except ET.ParseError:
        pass
    return rare


# ---------------------------------------------------------------------------
# Parse Orphadata product1: alignments → OrphaCode ↔ MONDO / OMIM
# ---------------------------------------------------------------------------

def parse_product1_alignments(xml_path: Path) -> tuple:
    """Return (orpha_to_mondo, orpha_to_omim) dicts.
    orpha_to_mondo: {orpha_code: set of mondo_ids}
    orpha_to_omim:  {orpha_code: set of omim_ids}
    """
    orpha_to_mondo = {}
    orpha_to_omim = {}
    if not xml_path.exists():
        return orpha_to_mondo, orpha_to_omim
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for disorder in root.findall(".//Disorder"):
            oc = disorder.find("OrphaCode")
            if oc is None or not oc.text:
                continue
            code = oc.text.strip()
            erl = disorder.find("ExternalReferenceList")
            if erl is None:
                continue
            for ref in erl.findall("ExternalReference"):
                src_el = ref.find("Source")
                val_el = ref.find("Reference")
                if src_el is None or val_el is None:
                    continue
                src = (src_el.text or "").strip()
                val = (val_el.text or "").strip()
                if src == "MONDO":
                    orpha_to_mondo.setdefault(code, set()).add(val)
                elif src == "OMIM":
                    orpha_to_omim.setdefault(code, set()).add(val)
    except ET.ParseError:
        pass
    return orpha_to_mondo, orpha_to_omim


# ---------------------------------------------------------------------------
# Parse Orphadata product4: HPO phenotype annotations
# ---------------------------------------------------------------------------

def parse_product4_hpo(xml_path: Path) -> dict:
    """Return {orpha_code: [(hpo_id, hpo_term, frequency_label), ...]}."""
    hpo_map = {}
    if not xml_path.exists():
        return hpo_map
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for disorder in root.findall(".//Disorder"):
            oc = disorder.find("OrphaCode")
            if oc is None or not oc.text:
                continue
            code = oc.text.strip()
            assoc_list = disorder.find("HPODisorderAssociationList")
            if assoc_list is None:
                continue
            anns = []
            for assoc in assoc_list.findall("HPODisorderAssociation"):
                hpo_el = assoc.find("HPO")
                if hpo_el is None:
                    continue
                hpo_id_el = hpo_el.find("HPOId")
                hpo_term_el = hpo_el.find("HPOTerm")
                freq_el = assoc.find("HPOFrequency")
                hpo_id = hpo_id_el.text.strip() if hpo_id_el is not None and hpo_id_el.text else None
                hpo_term = hpo_term_el.text.strip() if hpo_term_el is not None and hpo_term_el.text else ""
                freq = "unknown"
                if freq_el is not None:
                    fn = freq_el.find("Name")
                    if fn is not None and fn.text:
                        freq = fn.text.strip()
                if hpo_id:
                    anns.append((hpo_id, hpo_term, freq))
            if anns:
                hpo_map[code] = anns
    except ET.ParseError:
        pass
    return hpo_map


# ---------------------------------------------------------------------------
# Build maps: PrimeKG disease → is_rare, orphanet_id, HPO annotations
# ---------------------------------------------------------------------------

def _build_mondo_to_orpha(orpha_to_mondo: dict) -> dict:
    """Invert orpha_to_mondo → {mondo_id: orpha_code} (first match wins)."""
    mondo_to_orpha = {}
    for orpha, mondos in orpha_to_mondo.items():
        for m in mondos:
            if m not in mondo_to_orpha:
                mondo_to_orpha[m] = orpha
    return mondo_to_orpha


def _normalize_name(name: str) -> str:
    return (name or "").lower().strip()


def build_maps(disease_nodes: pd.DataFrame, rare_orphacodes: dict,
               orpha_to_mondo: dict, orpha_to_omim: dict,
               hpo_annotations: dict) -> tuple:
    """Map PrimeKG disease nodes to Orphanet, tag as rare, attach HPO.
    Returns (rare_mask, orphanet_map, hpo_map)."""

    mondo_to_orpha = _build_mondo_to_orpha(orpha_to_mondo)
    rare_set = set(rare_orphacodes.keys())

    # Also build name→orpha for fuzzy fallback
    name_to_orpha = {}
    for oc, nm in rare_orphacodes.items():
        key = _normalize_name(nm)
        if key:
            name_to_orpha[key] = oc

    rare_mask = {}
    orphanet_map = {}
    hpo_map = {}

    for _, row in disease_nodes.iterrows():
        nid = str(row["node_id"])
        node_name = str(row.get("node_name", ""))
        orpha = None

        # Strategy 1: PrimeKG node_id is a single MONDO id → direct lookup
        if nid in mondo_to_orpha:
            orpha = mondo_to_orpha[nid]
        else:
            # Strategy 2: node_id is a grouped MONDO id (e.g. "1200_1134_...")
            # Check each component
            for part in nid.split("_"):
                p = part.strip()
                if p in mondo_to_orpha:
                    orpha = mondo_to_orpha[p]
                    break

        # Strategy 3: fallback via disease name matching
        if not orpha:
            key = _normalize_name(node_name)
            if key in name_to_orpha:
                orpha = name_to_orpha[key]

        if orpha:
            orphanet_map[nid] = orpha
            rare_mask[nid] = orpha in rare_set
        else:
            rare_mask[nid] = False

        # Attach HPO annotations
        if orpha and orpha in hpo_annotations:
            hpo_map[nid] = [(hid, freq) for hid, _, freq in hpo_annotations[orpha]]

    return rare_mask, orphanet_map, hpo_map


# ---------------------------------------------------------------------------
# run_phase2
# ---------------------------------------------------------------------------

def run_phase2(save: bool = True) -> tuple:
    paths = get_paths()
    processed = paths.processed / "disease_nodes.csv"
    if not processed.exists():
        raise FileNotFoundError("Run phase1 first to create disease_nodes.csv")
    disease_nodes = pd.read_csv(processed)

    # --- Parse Orphadata XMLs ---
    product9 = paths.raw_orphanet / "en_product9_prev.xml"
    product1 = paths.raw_orphanet / "en_product1.xml"
    product4 = paths.raw_orphanet / "en_product4.xml"

    print("  Parsing en_product9_prev.xml (rare disease list)...")
    rare_orphacodes = parse_product9_rare_diseases(product9)
    print(f"    {len(rare_orphacodes)} rare diseases in Orphanet epidemiology DB")

    print("  Parsing en_product1.xml (alignments: MONDO/OMIM cross-refs)...")
    orpha_to_mondo, orpha_to_omim = parse_product1_alignments(product1)
    mondo_to_orpha = _build_mondo_to_orpha(orpha_to_mondo)
    print(f"    {len(orpha_to_mondo)} orphacodes with MONDO refs, "
          f"{len(mondo_to_orpha)} unique MONDO→Orpha mappings")

    print("  Parsing en_product4.xml (HPO phenotype annotations)...")
    hpo_annotations = parse_product4_hpo(product4)
    print(f"    {len(hpo_annotations)} disorders with HPO annotations, "
          f"{sum(len(v) for v in hpo_annotations.values())} total annotations")

    # --- Build maps ---
    print("  Mapping PrimeKG diseases to Orphanet...")
    rare_mask, orphanet_map, hpo_map = build_maps(
        disease_nodes, rare_orphacodes, orpha_to_mondo, orpha_to_omim, hpo_annotations)

    n_rare = sum(1 for v in rare_mask.values() if v)
    n_mapped = len(orphanet_map)
    n_hpo = len(hpo_map)
    print(f"    PrimeKG diseases: {len(disease_nodes)}")
    print(f"    Mapped to Orphanet: {n_mapped}")
    print(f"    Tagged as rare: {n_rare}")
    print(f"    With HPO annotations: {n_hpo}")

    if save:
        paths.processed.mkdir(parents=True, exist_ok=True)
        pd.DataFrame([{"node_id": k, "is_rare": v} for k, v in rare_mask.items()]).to_csv(
            paths.processed / "disease_rare_mask.csv", index=False)
        pd.DataFrame([{"node_id": k, "orphanet_id": v} for k, v in orphanet_map.items() if v]).to_csv(
            paths.processed / "disease_orphanet_map.csv", index=False)
        rows = [{"node_id": nid, "hpo_id": hpo_id, "frequency": freq}
                for nid, anns in hpo_map.items() for hpo_id, freq in anns]
        if rows:
            pd.DataFrame(rows).to_csv(paths.processed / "disease_hpo_annotations.csv", index=False)
        else:
            pd.DataFrame(columns=["node_id", "hpo_id", "frequency"]).to_csv(
                paths.processed / "disease_hpo_annotations.csv", index=False)

    return rare_mask, orphanet_map, hpo_map
