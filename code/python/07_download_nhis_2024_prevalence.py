"""Download NHIS 2024 current-prevalence inputs.

Preferred source is IPUMS NHIS because STRONGFWK is harmonized. If IPUMS is not
available or the extract fails, the script falls back to the official CDC/NCHS
2024 Sample Adult public-use files. The IPUMS API key is never printed or saved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data/raw/nhis_2024"
INTERIM_DIR = PROJECT_ROOT / "data/interim/nhis_2024"
PROCESSED_DIR = PROJECT_ROOT / "data/processed/nhis_2024"
DOCS_DIR = PROJECT_ROOT / "docs"
LOG_DIR = PROJECT_ROOT / "outputs/logs"

LOG_FILE = LOG_DIR / "07_download_nhis_2024_prevalence.log"
ISSUES = LOG_DIR / "issues_to_resolve.md"
MANUAL_DOC = DOCS_DIR / "NHIS_2024_download_instructions.md"

COLLECTION = "nhis"
API_VERSION = "2"
API_BASE = "https://api.ipums.org/extracts"
IPUMS_SAMPLE = "ih2024"

IPUMS_VARIABLES = [
    "YEAR",
    "SERIAL",
    "NHISPID",
    "ASTATFLG",
    "STRATA",
    "PSU",
    "SAMPWEIGHT",
    "AGE",
    "SEX",
    "RACEA",
    "HISPETH",
    "EDUC",
    "POVERTY",
    "REGION",
    "STRONGFNO",
    "STRONGFTP",
    "STRONGFWK",
    "MOD10FWK",
    "MOD10DMIN",
    "VIG10FWK",
    "VIG10DMIN",
    "PA18AERSTR",
]

CDC_2024_FILES = {
    "adult_csv_zip": "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Datasets/NHIS/2024/adult24csv.zip",
    "adult_codebook_pdf": "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Dataset_Documentation/NHIS/2024/adult-codebook.pdf",
    "adult_summary_pdf": "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Dataset_Documentation/NHIS/2024/adult-summary.pdf",
    "adult_stata_zip": "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Datasets/NHIS/2024/adult24stata.zip",
    "metadata_xml": "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Dataset_Documentation/NHIS/2024/adult-metadata.xml",
}

OFFICIAL_SOURCES = [
    "CDC/NCHS 2024 NHIS documentation: https://www.cdc.gov/nchs/nhis/documentation/2024-nhis.html",
    "IPUMS NHIS STRONGFWK: https://nhis.ipums.org/nhis-action/variables/STRONGFWK",
    "IPUMS NHIS PA18AERSTR: https://nhis.ipums.org/nhis-action/variables/PA18AERSTR",
]


def ensure_dirs() -> None:
    for path in [RAW_DIR, INTERIM_DIR, PROCESSED_DIR, DOCS_DIR, LOG_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def log(message: str) -> None:
    ensure_dirs()
    stamp = datetime.now().isoformat(timespec="seconds")
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(f"[{stamp}] {message}\n")
    print(message)


def append_issue_once(title: str, message: str) -> None:
    ensure_dirs()
    old = ISSUES.read_text(encoding="utf-8") if ISSUES.exists() else "# Issues to Resolve\n\n"
    if title in old:
        return
    with ISSUES.open("w", encoding="utf-8") as handle:
        handle.write(old.rstrip() + "\n\n")
        handle.write(f"## {datetime.now().isoformat(timespec='seconds')} - {title}\n\n")
        handle.write(message.rstrip() + "\n")


def sanitized_error_text(error: BaseException, api_key: str | None = None) -> str:
    if isinstance(error, requests.HTTPError) and error.response is not None:
        response = error.response
        body = response.text.strip()
        message = f"HTTP {response.status_code} {response.reason} for {response.url}"
        if body:
            message = f"{message}\n\n{body}"
    else:
        message = str(error)
    if api_key:
        message = message.replace(api_key, "[REDACTED_IPUMS_API_KEY]")
    return message


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def existing_usable_files() -> bool:
    has_ipums = any(RAW_DIR.glob("*.csv.gz")) and any(RAW_DIR.glob("*.xml"))
    has_cdc = any(RAW_DIR.glob("adult24csv.zip")) or any(RAW_DIR.glob("adult*.csv"))
    return bool(has_ipums or has_cdc)


def extract_payload() -> dict:
    return {
        "description": "MSA burden US: NHIS 2024 current MSA prevalence extract",
        "dataStructure": {"rectangular": {"on": "P"}},
        "dataFormat": "csv",
        "samples": {IPUMS_SAMPLE: {}},
        "variables": {var: {} for var in IPUMS_VARIABLES},
    }


def filename_from_url(url: str, fallback: str) -> str:
    name = Path(urlparse(url).path).name
    return name or fallback


def submit_ipums_extract(api_key: str) -> dict:
    response = requests.post(
        f"{API_BASE}?collection={COLLECTION}&version={API_VERSION}",
        headers={"Authorization": api_key, "Content-Type": "application/json"},
        data=json.dumps(extract_payload()),
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def get_ipums_extract(api_key: str, number: int) -> dict:
    response = requests.get(
        f"{API_BASE}/{number}?collection={COLLECTION}&version={API_VERSION}",
        headers={"Authorization": api_key, "Content-Type": "application/json"},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def download_ipums_links(api_key: str, status: dict) -> list[Path]:
    downloaded: list[Path] = []
    links = status.get("downloadLinks") or status.get("download_links") or {}
    for link_name, info in links.items():
        url = info.get("url")
        if not url:
            continue
        out_name = filename_from_url(url, f"ipums_nhis_2024_{status['number']}_{link_name}")
        out_path = RAW_DIR / out_name
        with requests.get(url, headers={"Authorization": api_key}, stream=True, timeout=120) as response:
            response.raise_for_status()
            with out_path.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        handle.write(chunk)
        expected = info.get("sha256")
        if expected and sha256(out_path) != expected:
            raise RuntimeError(f"SHA256 mismatch for {out_path.name}")
        downloaded.append(out_path)
    return downloaded


def download_from_ipums(api_key: str, poll_seconds: int, max_wait_minutes: int) -> bool:
    payload_path = RAW_DIR / "ipums_nhis_2024_extract_payload.json"
    payload_path.write_text(json.dumps(extract_payload(), indent=2) + "\n", encoding="utf-8")
    try:
        submitted = submit_ipums_extract(api_key)
        number = int(submitted["number"])
        (LOG_DIR / "ipums_nhis_2024_extract_submitted.json").write_text(json.dumps(submitted, indent=2) + "\n", encoding="utf-8")
        log(f"Submitted IPUMS NHIS 2024 extract {number}; polling for completion.")
        deadline = time.time() + max_wait_minutes * 60
        status = submitted
        while time.time() < deadline:
            status = get_ipums_extract(api_key, number)
            (LOG_DIR / "ipums_nhis_2024_extract_status_latest.json").write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
            state = str(status.get("status", "")).lower()
            log(f"IPUMS NHIS 2024 extract {number} status: {state}")
            if state in {"completed", "produced"}:
                downloaded = download_ipums_links(api_key, status)
                metadata = {
                    "source": "ipums",
                    "extract_number": number,
                    "sample": IPUMS_SAMPLE,
                    "variables": IPUMS_VARIABLES,
                    "downloaded_files": [str(path.relative_to(PROJECT_ROOT)) for path in downloaded],
                    "official_sources": OFFICIAL_SOURCES,
                }
                (INTERIM_DIR / "nhis_2024_download_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
                log("Downloaded IPUMS NHIS 2024 files: " + ", ".join(path.name for path in downloaded))
                return True
            if state in {"failed", "canceled", "cancelled"}:
                append_issue_once(
                    "IPUMS NHIS 2024 extract failed",
                    f"IPUMS NHIS 2024 extract {number} ended with status `{state}`. The script will try CDC public-use files. Latest sanitized status was saved without the API key.",
                )
                return False
            time.sleep(poll_seconds)
        append_issue_once(
            "IPUMS NHIS 2024 extract timeout",
            f"IPUMS NHIS 2024 extract {number} did not complete within {max_wait_minutes} minutes. The script will try CDC public-use files.",
        )
        return False
    except Exception as error:
        append_issue_once(
            "IPUMS NHIS 2024 download failed",
            "The IPUMS NHIS 2024 download failed. No API key was printed or saved. Sanitized error:\n\n"
            "```text\n"
            f"{sanitized_error_text(error, api_key)}\n"
            "```",
        )
        log("IPUMS NHIS 2024 download failed; falling back to CDC public-use files.")
        return False


def download_file(url: str, out_path: Path) -> None:
    with requests.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()
        with out_path.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)


def download_from_cdc() -> bool:
    downloaded: list[Path] = []
    for label, url in CDC_2024_FILES.items():
        out_path = RAW_DIR / filename_from_url(url, f"{label}.dat")
        try:
            download_file(url, out_path)
            downloaded.append(out_path)
            log(f"Downloaded CDC file: {out_path.name}")
        except Exception as error:
            append_issue_once(
                f"CDC NHIS 2024 file download failed: {label}",
                f"Could not download `{url}`. Sanitized error:\n\n```text\n{sanitized_error_text(error)}\n```",
            )
            log(f"CDC file download failed for {label}; continuing with remaining files.")

    has_data = any(path.name.lower() == "adult24csv.zip" for path in downloaded) or any(path.suffix.lower() == ".csv" for path in downloaded)
    has_codebook = any("codebook" in path.name.lower() for path in downloaded)
    if not (has_data and has_codebook):
        write_manual_instructions()
        append_issue_once(
            "NHIS 2024 manual download required",
            "`code/python/07_download_nhis_2024_prevalence.py` could not automatically obtain both the CDC Sample Adult data and codebook. Manual instructions were written to `docs/NHIS_2024_download_instructions.md`.",
        )
        return False

    metadata = {
        "source": "cdc",
        "downloaded_files": [str(path.relative_to(PROJECT_ROOT)) for path in downloaded],
        "official_sources": OFFICIAL_SOURCES,
    }
    (INTERIM_DIR / "nhis_2024_download_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return True


def write_manual_instructions() -> None:
    sources = "\n".join(f"- {source}" for source in OFFICIAL_SOURCES)
    MANUAL_DOC.write_text(
        f"""# NHIS 2024 Manual Download Instructions

Generated: {datetime.now().isoformat(timespec="seconds")}

Automatic IPUMS and CDC downloads did not produce a complete usable NHIS 2024
Sample Adult prevalence input. Do not fabricate data.

Download these official files manually and place them in `data/raw/nhis_2024/`:

- CDC/NCHS 2024 NHIS Sample Adult CSV public-use file
- CDC/NCHS 2024 NHIS Sample Adult codebook
- Optional CDC/NCHS Sample Adult Stata statements or metadata XML

Preferred source:

https://www.cdc.gov/nchs/nhis/documentation/2024-nhis.html

The build script will look for either an IPUMS extract with `STRONGFWK` or the
CDC Sample Adult file with the strengthening frequency variable documented in
the codebook.

Official sources checked:

{sources}
""",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument("--max-wait-minutes", type=int, default=90)
    parser.add_argument("--force", action="store_true", help="Submit/download even if raw NHIS 2024 files already exist.")
    args = parser.parse_args()

    ensure_dirs()
    LOG_FILE.write_text(f"NHIS 2024 prevalence download log started {datetime.now().isoformat(timespec='seconds')}\n", encoding="utf-8")

    if existing_usable_files() and not args.force:
        log("Existing NHIS 2024 raw files detected; skipping download. Use --force to redownload.")
        return

    api_key = os.environ.get("IPUMS_API_KEY")
    if api_key:
        log("IPUMS_API_KEY is present; attempting IPUMS NHIS 2024 extract. The key will not be logged.")
        if download_from_ipums(api_key, args.poll_seconds, args.max_wait_minutes):
            return
    else:
        append_issue_once(
            "IPUMS_API_KEY unavailable for NHIS 2024",
            "`IPUMS_API_KEY` was not available for the NHIS 2024 current prevalence extract. The script attempted CDC public-use download instead.",
        )
        log("IPUMS_API_KEY not available; attempting CDC public-use download.")

    if download_from_cdc():
        log("CDC/NCHS NHIS 2024 public-use files downloaded.")
    else:
        raise SystemExit("NHIS 2024 automatic download failed. See docs/NHIS_2024_download_instructions.md.")


if __name__ == "__main__":
    main()
