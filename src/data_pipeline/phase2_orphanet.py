"""
Phase 2: Layer 1 - Rare disease filter (Orphanet).
Tag disease nodes as is_rare, add Orphanet ID and HPO annotations.
"""
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import pandas as pd

from .config import get_paths

ORPHA_PATTERN = re.compile(r"ORPHA(\d+)")


def _mondo_to_orphanet_from_obo(obo_path: Path) -> dict:
    mondo_to_orpha = {}
    if not obo_path.exists():
        return mondo_to_orpha
    current_id = None
    with open(obo_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("id:"):
                current_id = line.split(":", 1)[1].strip()
            elif line.startswith("xref:") and current_id and "Orphanet" in line:
                for part in line.split(":", 2)[-1].split(","):
                    part = part.strip()
                    if part.startswith("Orphanet:"):
                        orpha = part.replace("Orphanet:", "").strip()
                        mondo_to_orpha[current_id] = "ORPHA" + orpha if not orpha.startswith("ORPHA") else orpha
                current_id = None
    return mondo_to_orpha


def _parse_orphanet_xml(xml_path: Path) -> set:
    rare_ids = set()
    if not xml_path.exists():
        return rare_ids
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for disorder in root.findall(".//Disorder") or root.findall(".//disorder"):
            code = disorder.find("OrphaCode") or disorder.find("code")
            if code is not None and code.text:
                c = code.text.strip()
                rare_ids.add("ORPHA" + c if c.isdigit() else c)
    except ET.ParseError:
        pass
    return rare_ids


def load_rare_disease_mondo_set(paths) -> set:
    orpha_xml = paths.raw_orphanet / "en_product6_prev.xml"
    if not orpha_xml.exists():
        for f in paths.raw_orphanet.glob("*.xml"):
            orpha_xml = f
            break
    rare_orpha = _parse_orphanet_xml(orpha_xml)
    if not rare_orpha and (paths.raw_orphanet / "rare_disease_list.txt").exists():
        rare_orpha = set(line.strip() for line in open(paths.raw_orphanet / "rare_disease_list.txt") if line.strip())
    rare_orpha = {o if str(o).startswith("ORPHA") else "ORPHA" + str(o) for o in rare_orpha if o}
    mondo_obo = paths.raw_mondo / "mondo.obo"
    if not mondo_obo.exists():
        mondo_obo = paths.raw_orphanet / "mondo.obo"
    mondo_to_orpha = _mondo_to_orphanet_from_obo(mondo_obo)
    return {mondo for mondo, orpha in mondo_to_orpha.items() if orpha in rare_orpha}


def load_hpo_annotations(paths) -> dict:
    out = {}
    hpo_path = paths.raw_orphanet / "en_product6_prev_HPO.xml"
    if not hpo_path.exists():
        for f in paths.raw_orphanet.glob("*HPO*"):
            hpo_path = f
            break
    if not hpo_path.exists():
        return out
    try:
        tree = ET.parse(hpo_path)
        root = tree.getroot()
        for disorder in root.findall(".//Disorder") or root.findall(".//disorder"):
            orpha = None
            for code in disorder.findall("OrphaCode") or disorder.findall("code"):
                if code.text:
                    orpha = "ORPHA" + code.text.strip() if code.text.strip().isdigit() else code.text.strip()
                    break
            if not orpha:
                continue
            anns = []
            for hpo in disorder.findall(".//HPO") or disorder.findall(".//HPOId") or []:
                hpo_id = hpo.text or hpo.get("id") or hpo.get("HPOId")
                freq = hpo.get("frequency") or "unknown"
                if hpo_id:
                    anns.append((hpo_id.strip(), freq))
            if anns:
                out[orpha] = anns
    except ET.ParseError:
        pass
    return out


def build_maps(disease_nodes: pd.DataFrame, rare_mondo_set: set, hpo_annotations: dict, mondo_to_orpha: dict) -> tuple:
    rare_mask = {}
    orphanet_map = {}
    hpo_map = {}
    for _, row in disease_nodes.iterrows():
        nid = row["node_id"]
        rare_mask[nid] = nid in rare_mondo_set
        if nid in mondo_to_orpha:
            orphanet_map[nid] = mondo_to_orpha[nid]
        elif str(nid).startswith("ORPHA"):
            orphanet_map[nid] = nid
        oid = orphanet_map.get(nid) or nid
        if oid in hpo_annotations:
            hpo_map[nid] = hpo_annotations[oid]
    return rare_mask, orphanet_map, hpo_map


def run_phase2(save: bool = True) -> tuple:
    paths = get_paths()
    processed = paths.processed / "disease_nodes.csv"
    if not processed.exists():
        raise FileNotFoundError("Run phase1 first to create disease_nodes.csv")
    disease_nodes = pd.read_csv(processed)
    mondo_obo = paths.raw_mondo / "mondo.obo"
    if not mondo_obo.exists():
        mondo_obo = paths.raw_orphanet / "mondo.obo"
    mondo_to_orpha = _mondo_to_orphanet_from_obo(mondo_obo)
    rare_mondo_set = load_rare_disease_mondo_set(paths)
    hpo_annotations = load_hpo_annotations(paths)
    rare_mask, orphanet_map, hpo_map = build_maps(disease_nodes, rare_mondo_set, hpo_annotations, mondo_to_orpha)
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
    return rare_mask, orphanet_map, hpo_map
