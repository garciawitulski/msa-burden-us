"""Create the MSA burden US project skeleton and check dependencies."""

from __future__ import annotations

import importlib.util
import os
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DIRECTORIES = [
    "data/raw",
    "data/interim",
    "data/processed",
    "data/external",
    "code/python",
    "code/stata",
    "code/r",
    "docs",
    "outputs/tables",
    "outputs/figures",
    "outputs/logs",
]

REQUIRED_PACKAGES = ["pandas", "numpy", "pyreadstat"]
OPTIONAL_PACKAGES = ["requests"]


def package_status(package: str) -> str:
    return "OK" if importlib.util.find_spec(package) is not None else "MISSING"


def main() -> None:
    for rel_path in DIRECTORIES:
        (PROJECT_ROOT / rel_path).mkdir(parents=True, exist_ok=True)

    lines = [
        f"Setup check run at: {datetime.now().isoformat(timespec='seconds')}",
        f"Project root: {PROJECT_ROOT}",
        "",
        "Dependency check:",
    ]
    for package in REQUIRED_PACKAGES:
        lines.append(f"- {package}: {package_status(package)}")
    for package in OPTIONAL_PACKAGES:
        lines.append(f"- {package} (optional): {package_status(package)}")

    key_status = "SET" if os.environ.get("IPUMS_API_KEY") else "NOT_SET"
    lines.extend(
        [
            "",
            f"IPUMS_API_KEY: {key_status}",
            "",
            "Created/verified directories:",
        ]
    )
    lines.extend(f"- {rel_path}" for rel_path in DIRECTORIES)

    log_path = PROJECT_ROOT / "outputs/logs/setup_check.txt"
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
