"""Load paths and settings from configs/paths.yaml."""
from pathlib import Path
import os

try:
    import yaml
except ImportError:
    yaml = None

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_PATH = _PROJECT_ROOT / "configs" / "paths.yaml"


def load_config():
    if yaml is None:
        raise ImportError("Install pyyaml: pip install pyyaml")
    if not _CONFIG_PATH.exists():
        return {"project_root": str(_PROJECT_ROOT), "data": {}, "raw_subdirs": {}}
    with open(_CONFIG_PATH) as f:
        cfg = yaml.safe_load(f) or {}
    root = cfg.get("project_root", ".")
    if not Path(root).is_absolute():
        root = _PROJECT_ROOT / root
    cfg["project_root"] = Path(root).resolve()
    return cfg


def get_paths():
    cfg = load_config()
    root = cfg["project_root"]
    data = cfg.get("data", {})
    raw = root / data.get("raw", "data/raw")
    processed = root / data.get("processed", "data/processed")
    enriched = root / data.get("enriched", "data/enriched")
    splits = root / data.get("splits", "data/splits")
    subdirs = cfg.get("raw_subdirs", {})
    return type("Paths", (), {
        "root": root,
        "raw": root / data.get("raw", "data/raw"),
        "processed": root / data.get("processed", "data/processed"),
        "enriched": root / data.get("enriched", "data/enriched"),
        "splits": root / data.get("splits", "data/splits"),
        "raw_primekg": raw / subdirs.get("primekg", "primekg"),
        "raw_orphanet": raw / subdirs.get("orphanet", "orphanet"),
        "raw_clinvar": raw / subdirs.get("clinvar", "clinvar"),
        "raw_gnomad": raw / subdirs.get("gnomad", "gnomad"),
        "raw_drugbank": raw / subdirs.get("drugbank", "drugbank"),
        "raw_sider": raw / subdirs.get("sider", "sider"),
        "raw_hgnc": raw / subdirs.get("hgnc", "hgnc"),
        "raw_mondo": raw / subdirs.get("mondo", "mondo"),
    })()
