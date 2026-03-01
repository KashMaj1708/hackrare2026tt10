#!/usr/bin/env python3
"""
Download full PrimeKG from Harvard Dataverse (doi:10.7910/DVN/IXA7BM).
Saves kg.csv (main graph, ~937 MB) to data/raw/primekg/kg.csv.
"""
import os
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("Install requests: pip install requests")
    sys.exit(1)

# Dataverse file IDs from dataset API (version 2)
PRIMEKG_FILES = {
    "kg.csv": 6180620,           # ~937 MB, main knowledge graph
    "edges.csv": 6180616,        # ~369 MB, edge list
    "nodes.tab": 6180617,        # ~8.5 MB, nodes (tab)
    "disease_features.tab": 6180618,
    "drug_features.tab": 6180619,
}

BASE_URL = "https://dataverse.harvard.edu/api/access/datafile"


def download_file(file_id: int, dest: Path, desc: str = "") -> bool:
    url = f"{BASE_URL}/{file_id}"
    print(f"Downloading {desc or dest.name} ...")
    try:
        r = requests.get(url, stream=True, timeout=30)
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        written = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=2**20):  # 1 MB
                if chunk:
                    f.write(chunk)
                    written += len(chunk)
                if total and written % (50 * 2**20) == 0 and written:
                    pct = 100 * written / total
                    print(f"  {written // 2**20} MB ({pct:.1f}%)")
        print(f"  Saved to {dest} ({written // 2**20} MB)")
        return True
    except Exception as e:
        print(f"  Error: {e}")
        if dest.exists():
            dest.unlink()
        return False


def main():
    root = Path(__file__).resolve().parents[1]
    out_dir = root / "data" / "raw" / "primekg"
    out_dir.mkdir(parents=True, exist_ok=True)

    # By default download only kg.csv (required for pipeline)
    targets = [("kg.csv", PRIMEKG_FILES["kg.csv"])]
    if os.environ.get("PRIMEKG_FULL") == "1":
        targets = [(k, v) for k, v in PRIMEKG_FILES.items()]

    for name, file_id in targets:
        dest = out_dir / name
        if dest.exists() and dest.stat().st_size > 100_000_000:  # already have ~100MB+
            print(f"Skip {name} (already exists, size {dest.stat().st_size // 2**20} MB)")
            continue
        ok = download_file(file_id, dest, name)
        if not ok:
            sys.exit(1)
    print("Done.")


if __name__ == "__main__":
    main()
