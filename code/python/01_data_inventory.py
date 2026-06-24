"""Inventory raw files and available IPUMS metadata/codebooks."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data/raw"
EXTERNAL_DIR = PROJECT_ROOT / "data/external"
DOCS_DIR = PROJECT_ROOT / "docs"
LOG_DIR = PROJECT_ROOT / "outputs/logs"

METADATA_EXTENSIONS = {".xml", ".cbk", ".do", ".sas", ".sps", ".json", ".txt", ".md"}
DATA_EXTENSIONS = {".csv", ".gz", ".dta", ".dat", ".sav", ".por", ".parquet", ".feather"}


def iter_files(paths: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.exists():
            files.extend(p for p in path.rglob("*") if p.is_file())
    return sorted(files)


def classify_file(path: Path) -> str:
    suffixes = "".join(path.suffixes).lower()
    if path.suffix.lower() in METADATA_EXTENSIONS or suffixes.endswith(".xml"):
        return "metadata_or_codebook"
    if path.suffix.lower() in DATA_EXTENSIONS or suffixes.endswith(".csv.gz") or suffixes.endswith(".dat.gz"):
        return "data"
    return "other"


def main() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    files = iter_files([RAW_DIR, EXTERNAL_DIR, DOCS_DIR])
    rows = []
    for path in files:
        rows.append(
            {
                "path": str(path.relative_to(PROJECT_ROOT)),
                "folder": str(path.parent.relative_to(PROJECT_ROOT)),
                "file_name": path.name,
                "size_bytes": path.stat().st_size,
                "modified_time": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
                "role": classify_file(path),
            }
        )

    inventory = pd.DataFrame(rows)
    inventory_path = LOG_DIR / "raw_data_inventory.csv"
    inventory.to_csv(inventory_path, index=False)

    summary = {
        "run_time": datetime.now().isoformat(timespec="seconds"),
        "project_root": str(PROJECT_ROOT),
        "n_files": int(len(inventory)),
        "n_data_files": int((inventory["role"] == "data").sum()) if not inventory.empty else 0,
        "n_metadata_files": int((inventory["role"] == "metadata_or_codebook").sum()) if not inventory.empty else 0,
        "inventory_csv": str(inventory_path.relative_to(PROJECT_ROOT)),
    }
    (LOG_DIR / "raw_data_inventory_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )

    if inventory.empty:
        print("No files found in data/raw, data/external, or docs.")
    else:
        print(inventory.to_string(index=False))


if __name__ == "__main__":
    main()
