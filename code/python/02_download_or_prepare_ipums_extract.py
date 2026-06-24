"""Download an IPUMS NHIS extract or write manual extract instructions.

The script checks IPUMS_API_KEY. If the key is absent, it writes
docs/IPUMS_extract_request.md and stops without fabricating data.
If the key is present, it submits the extract, polls until completed,
and downloads all returned files into data/raw.
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
RAW_DIR = PROJECT_ROOT / "data/raw"
DOCS_DIR = PROJECT_ROOT / "docs"
LOG_DIR = PROJECT_ROOT / "outputs/logs"

COLLECTION = "nhis"
API_VERSION = "2"
API_BASE = "https://api.ipums.org/extracts"

# Widest planned extract for this first-stage mortality project.
# Rationale is documented in docs/IPUMS_extract_request.md.
SAMPLES = [f"ih{year}" for year in range(1997, 2019)]

VARIABLES = [
    # Identifiers and design
    "YEAR",
    "SERIAL",
    "NHISPID",
    "QUARTER",
    "ASTATFLG",
    "STRATA",
    "PSU",
    "SAMPWEIGHT",
    "PERWEIGHT",
    "MORTWT",
    "MORTWTSA",
    # Mortality linkage and outcomes
    "MORTELIG",
    "MORTSTAT",
    "MORTDODY",
    "MORTDODQ",
    "MORTUCODLD",
    "MORTUCOD",
    # Main MSA exposure and aerobic activity
    "STRONGFNO",
    "STRONGFTP",
    "STRONGFWK",
    "MOD10FNO",
    "MOD10FTP",
    "MOD10FWK",
    "MOD10DNO",
    "MOD10DTP",
    "MOD10DMIN",
    "VIG10FNO",
    "VIG10FTP",
    "VIG10FWK",
    "VIG10DNO",
    "VIG10DTP",
    "VIG10DMIN",
    # Demographics and socioeconomic covariates
    "AGE",
    "SEX",
    "RACEA",
    "HISPETH",
    "EDUC",
    "POVERTY",
    "MARSTAT",
    "REGION",
    # Health and behavioral covariates
    "BMICALC",
    "SMOKESTATUS2",
    "ALCSTAT1",
    "ALCSTAT2",
    "HEALTH",
    "DIABETICEV",
    "HYPERTENEV",
    "CHEARTDIEV",
    "HEARTATTEV",
    "STROKEV",
    "CANCEREV",
]

OFFICIAL_SOURCES = [
    "IPUMS API microdata docs: https://developer.ipums.org/docs/v2/apiprogram/apis/microdata/",
    "IPUMS API extract workflow: https://developer.ipums.org/docs/v2/workflows/create_extracts/microdata/",
    "IPUMS NHIS sample IDs: https://nhis.ipums.org/nhis-action/samples/sample_ids",
    "IPUMS NHIS STRONGFWK: https://nhis.ipums.org/nhis-action/variables/STRONGFWK",
    "IPUMS NHIS MORTELIG/Mortality group: https://nhis.ipums.org/nhis-action/variables/group/mortality_mortality",
    "IPUMS NHIS MORTWTSA: https://nhis.ipums.org/nhis-action/variables/MORTWTSA/ajax_enum_text",
    "IPUMS NHIS physical activity group: https://nhis.ipums.org/nhis-action/variables/group/behavior_pa",
    "NCHS public-use LMF description: https://nhis.ipums.org/nhis/resources/public-use-linked-mortality-file-description.pdf",
]


def extract_payload() -> dict:
    return {
        "description": "MSA burden US: NHIS 1997-2018 linked mortality extract for MSA dose-response prep",
        "dataStructure": {"rectangular": {"on": "P"}},
        "dataFormat": "csv",
        "samples": {sample: {} for sample in SAMPLES},
        "variables": {var: {} for var in VARIABLES},
    }


def manual_request_text() -> str:
    variables_block = "\n".join(f"- {var}" for var in VARIABLES)
    samples_block = "\n".join(f"- {sample} ({sample.removeprefix('ih')} NHIS)" for sample in SAMPLES)
    sources_block = "\n".join(f"- {source}" for source in OFFICIAL_SOURCES)
    return f"""# Manual IPUMS NHIS Extract Request

Generated: {datetime.now().isoformat(timespec="seconds")}

No IPUMS_API_KEY environment variable was available, so this project did not
download or fabricate any data. Create the extract manually from IPUMS Health
Surveys: NHIS, then place the downloaded data and all metadata/codebook files in
`data/raw/`.

## Dataset

- IPUMS Health Surveys: NHIS
- Unit of analysis: person records
- Extract structure: rectangularized on person records (`P`)
- Data format: CSV if available, with DDI XML and basic codebook included
- Stata command file should also be downloaded when offered

## Samples to select

Select the NHIS samples from 1997 through 2018. These are the widest planned
years for the first-stage dataset because the IPUMS documentation indicates
adult strengthening activity is available from 1997 onward, while the 2019 LMF
update includes NHIS mortality follow-up for participants through the 2018 NHIS.
The 1997 physical-activity variables need special review because some aerobic
variables begin in quarters 3-4.

{samples_block}

## Variables to select

Select these exact IPUMS NHIS variable mnemonics. Some identifiers/design flags
may be preselected automatically by IPUMS; keep them in the extract if offered.

{variables_block}

## Metadata/codebooks required before cleaning

Download and keep these files next to the data in `data/raw/`:

- DDI XML codebook
- Basic codebook
- Stata command file, if offered
- Any IPUMS extract JSON or request metadata

The cleaning script intentionally inspects the downloaded metadata/codebooks
before constructing variables. If a required variable cannot be verified from
the metadata and data columns, the script stops and writes
`outputs/logs/issues_to_resolve.md`.

## Public-use follow-up time note

The preferred survival time variable is an exact public-use person-month
follow-up variable if it is available in the extract. IPUMS NHIS mortality
documentation commonly exposes year/quarter of death variables (`MORTDODY`,
`MORTDODQ`) and final vital status (`MORTSTAT`). If exact person-month follow-up
is not in the IPUMS extract, the project script constructs an approximate
quarter-based follow-up time using `YEAR`, `QUARTER`, `MORTDODY`, and
`MORTDODQ`, and records this limitation in the variable dictionary and issue log.

## Year inclusion table to create after download

After data are downloaded, run:

```powershell
python code/python/01_data_inventory.py
python code/python/03_build_msa_survival_dataset.py
python code/python/04_quality_checks.py
```

The build and quality scripts will create a year inclusion table documenting
which survey years are included and why.

## Official documentation checked

{sources_block}
"""


def write_issue(message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / "issues_to_resolve.md"
    old = path.read_text(encoding="utf-8") if path.exists() else "# Issues to Resolve\n\n"
    with path.open("w", encoding="utf-8") as handle:
        handle.write(old.rstrip() + "\n\n")
        handle.write(f"## {datetime.now().isoformat(timespec='seconds')}\n\n")
        handle.write(message.rstrip() + "\n")


def sanitized_error_text(error: BaseException, api_key: str) -> str:
    if isinstance(error, requests.HTTPError) and error.response is not None:
        response = error.response
        body = response.text.strip()
        message = f"HTTP {response.status_code} {response.reason} for {response.url}"
        if body:
            message = f"{message}\n\n{body}"
    else:
        message = str(error)
    return message.replace(api_key, "[REDACTED_IPUMS_API_KEY]")


def write_api_failure_issue(stage: str, error: BaseException, api_key: str) -> None:
    write_issue(
        f"IPUMS API request failed during {stage}. No data were fabricated.\n\n"
        "Exact sanitized API error:\n\n"
        "```text\n"
        f"{sanitized_error_text(error, api_key)}\n"
        "```"
    )


def submit_extract(api_key: str) -> dict:
    response = requests.post(
        f"{API_BASE}?collection={COLLECTION}&version={API_VERSION}",
        headers={"Authorization": api_key, "Content-Type": "application/json"},
        data=json.dumps(extract_payload()),
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def get_extract(api_key: str, number: int) -> dict:
    response = requests.get(
        f"{API_BASE}/{number}?collection={COLLECTION}&version={API_VERSION}",
        headers={"Authorization": api_key, "Content-Type": "application/json"},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def filename_from_url(url: str, fallback: str) -> str:
    name = Path(urlparse(url).path).name
    return name or fallback


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_links(api_key: str, status: dict) -> list[Path]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []
    links = status.get("downloadLinks") or status.get("download_links") or {}
    for link_name, info in links.items():
        url = info.get("url")
        if not url:
            continue
        out_name = filename_from_url(url, f"{COLLECTION}_{status['number']}_{link_name}")
        out_path = RAW_DIR / out_name
        with requests.get(url, headers={"Authorization": api_key}, stream=True, timeout=60) as response:
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument("--max-wait-minutes", type=int, default=240)
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    payload_path = RAW_DIR / "ipums_nhis_extract_payload.json"
    payload_path.write_text(json.dumps(extract_payload(), indent=2) + "\n", encoding="utf-8")

    api_key = os.environ.get("IPUMS_API_KEY")
    if not api_key:
        request_path = DOCS_DIR / "IPUMS_extract_request.md"
        request_path.write_text(manual_request_text(), encoding="utf-8")
        write_issue(
            "No IPUMS_API_KEY was available. A manual extract request was written to "
            "`docs/IPUMS_extract_request.md`. Processed datasets cannot be created until "
            "the IPUMS NHIS data and codebooks are placed in `data/raw/`."
        )
        print(f"IPUMS_API_KEY not set. Wrote {request_path.relative_to(PROJECT_ROOT)}")
        return

    try:
        submitted = submit_extract(api_key)
    except requests.RequestException as error:
        write_api_failure_issue("extract submission", error, api_key)
        raise
    number = int(submitted["number"])
    (LOG_DIR / "ipums_extract_submitted.json").write_text(
        json.dumps(submitted, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Submitted IPUMS NHIS extract {number}; polling for completion.")

    deadline = time.time() + args.max_wait_minutes * 60
    status = submitted
    while time.time() < deadline:
        try:
            status = get_extract(api_key, number)
        except requests.RequestException as error:
            write_api_failure_issue(f"polling extract {number}", error, api_key)
            raise
        (LOG_DIR / "ipums_extract_status_latest.json").write_text(
            json.dumps(status, indent=2) + "\n",
            encoding="utf-8",
        )
        state = str(status.get("status", "")).lower()
        print(f"Extract {number} status: {state}")
        if state in {"completed", "produced"}:
            try:
                downloaded = download_links(api_key, status)
            except requests.RequestException as error:
                write_api_failure_issue(f"downloading extract {number}", error, api_key)
                raise
            print("Downloaded files:")
            for path in downloaded:
                print(f"- {path.relative_to(PROJECT_ROOT)}")
            return
        if state in {"failed", "canceled", "cancelled"}:
            write_issue(
                f"IPUMS extract {number} ended with status: {state}. No data were fabricated.\n\n"
                "Latest status payload:\n\n"
                "```json\n"
                f"{json.dumps(status, indent=2)}\n"
                "```"
            )
            raise RuntimeError(f"IPUMS extract {number} ended with status: {state}")
        time.sleep(args.poll_seconds)

    raise TimeoutError(f"IPUMS extract {number} did not complete within max wait time.")


if __name__ == "__main__":
    main()
