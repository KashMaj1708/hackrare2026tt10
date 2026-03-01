#!/usr/bin/env python3
"""
Download Orphadata scientific knowledge XML files (CC BY 4.0).
Source: https://sciences.orphadata.com/orphanet-scientific-knowledge-files/

Files downloaded:
  - en_product9_prev.xml  -> Epidemiology (rare disease list + prevalence)
  - en_product1.xml       -> Alignments (OMIM, MONDO, UMLS cross-refs)
  - en_product4.xml       -> HPO phenotype annotations
  - en_product6.xml       -> Gene-disease associations
"""
import sys
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data" / "raw" / "orphanet"

ORPHADATA_FILES = {
    "en_product9_prev.xml": "https://www.orphadata.com/data/xml/en_product9_prev.xml",
    "en_product1.xml":      "https://www.orphadata.com/data/xml/en_product1.xml",
    "en_product4.xml":      "https://www.orphadata.com/data/xml/en_product4.xml",
    "en_product6.xml":      "https://www.orphadata.com/data/xml/en_product6.xml",
}


def download_file(url: str, dest: Path, chunk_size: int = 1024 * 256):
    print(f"  Downloading {url} ...")
    resp = requests.get(url, stream=True, timeout=120)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0))
    downloaded = 0
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=chunk_size):
            f.write(chunk)
            downloaded += len(chunk)
            if total:
                pct = downloaded / total * 100
                print(f"\r    {downloaded / 1e6:.1f} / {total / 1e6:.1f} MB ({pct:.0f}%)", end="", flush=True)
    print(f"\n    -> Saved to {dest}  ({dest.stat().st_size / 1e6:.1f} MB)")


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    for fname, url in ORPHADATA_FILES.items():
        dest_path = DEST / fname
        if dest_path.exists() and dest_path.stat().st_size > 1000:
            print(f"  {fname} already exists ({dest_path.stat().st_size / 1e6:.1f} MB), skipping.")
            continue
        try:
            download_file(url, dest_path)
        except Exception as e:
            print(f"  ERROR downloading {fname}: {e}")
            sys.exit(1)
    print("\nAll Orphadata files downloaded successfully.")


if __name__ == "__main__":
    main()
