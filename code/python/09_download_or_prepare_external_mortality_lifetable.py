"""Download or prepare official mortality and life-table inputs.

This script creates external inputs for the NHIS 2024 current-prevalence burden
scenario. It uses official CDC/NCHS sources only:

* CDC WONDER Underlying Cause of Death, 2018-2024, Single Race (D158)
* NCHS United States Life Tables, 2023, NVSR 74(6)

No death counts or life expectancies are fabricated. If automatic download fails,
manual instructions are written and the script exits without creating analytic
inputs from placeholders.
"""

from __future__ import annotations

import argparse
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
import pandas as pd
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXTERNAL_DIR = PROJECT_ROOT / "data/external"
RAW_WONDER_DIR = EXTERNAL_DIR / "cdc_wonder_raw"
RAW_LIFE_DIR = EXTERNAL_DIR / "nchs_life_tables_2023"
DOCS_DIR = PROJECT_ROOT / "docs"
LOG_DIR = PROJECT_ROOT / "outputs/logs"

DEATHS_FILE = EXTERNAL_DIR / "us_allcause_deaths_by_age_sex.csv"
LIFE_FILE = EXTERNAL_DIR / "us_life_table_by_age_sex.csv"
LIFE_GROUP_FILE = EXTERNAL_DIR / "us_life_table_by_agegroup_sex.csv"
LOG_FILE = LOG_DIR / "09_external_mortality_lifetable.log"
ISSUES = LOG_DIR / "issues_to_resolve.md"

MORTALITY_MANUAL_DOC = DOCS_DIR / "external_mortality_manual_download_instructions.md"
LIFETABLE_MANUAL_DOC = DOCS_DIR / "external_lifetable_manual_download_instructions.md"

WONDER_ENDPOINT = "https://wonder.cdc.gov/controller/datarequest/D158"
WONDER_DATASET = "Underlying Cause of Death, 2018-2024, Single Race"
WONDER_SOURCE = (
    "CDC WONDER Underlying Cause of Death by Single Race 2018-2024, "
    "National Center for Health Statistics, released 2026"
)
WONDER_YEAR_PREFERENCES = [2024, 2023]

LIFE_TABLE_YEAR = 2023
LIFE_TABLE_SOURCE = "NCHS United States Life Tables, 2023, NVSR Volume 74, Number 6"
LIFE_TABLE_URLS = {
    "Male": "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/NVSR/74-06/Table02.xlsx",
    "Female": "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/NVSR/74-06/Table03.xlsx",
}

TARGET_AGE_GROUPS = ["18-34", "35-44", "45-54", "55-64", "65-74", "75+"]
TARGET_SEXES = ["Female", "Male"]

# Components are summed within each target age group. This avoids including ages
# 15-17 in the 18-34 group while keeping most queries in stable grouped-age form.
AGE_QUERY_COMPONENTS: dict[str, list[dict[str, object]]] = {
    "18-34": [
        {"age_var": "D158.V52", "values": ["18", "19"], "label": "single_year_18_19"},
        {"age_var": "D158.V51", "values": ["20-24", "25-29", "30-34"], "label": "five_year_20_34"},
    ],
    "35-44": [{"age_var": "D158.V5", "values": ["35-44"], "label": "ten_year_35_44"}],
    "45-54": [{"age_var": "D158.V5", "values": ["45-54"], "label": "ten_year_45_54"}],
    "55-64": [{"age_var": "D158.V5", "values": ["55-64"], "label": "ten_year_55_64"}],
    "65-74": [{"age_var": "D158.V5", "values": ["65-74"], "label": "ten_year_65_74"}],
    "75+": [{"age_var": "D158.V5", "values": ["75-84", "85+"], "label": "ten_year_75_plus"}],
}

REPRESENTATIVE_AGES = {
    "18-34": 25,
    "35-44": 40,
    "45-54": 50,
    "55-64": 60,
    "65-74": 70,
    "75+": 80,
}


def ensure_dirs() -> None:
    for path in [EXTERNAL_DIR, RAW_WONDER_DIR, RAW_LIFE_DIR, DOCS_DIR, LOG_DIR]:
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
    ISSUES.write_text(old.rstrip() + f"\n\n## {datetime.now().isoformat(timespec='seconds')} - {title}\n\n{message.rstrip()}\n", encoding="utf-8")


def stop(title: str, message: str) -> None:
    append_issue_once(title, message)
    raise SystemExit(message)


def has_required_columns(path: Path, required: list[str]) -> bool:
    if not path.exists():
        return False
    try:
        header = pd.read_csv(path, nrows=0).columns.tolist()
    except Exception:
        return False
    return all(col in header for col in required)


def parameter(name: str, values: str | list[str]) -> str:
    if not isinstance(values, list):
        values = [values]
    value_xml = "".join(f"<value>{escape(str(value))}</value>" for value in values)
    return f"<parameter><name>{escape(name)}</name>{value_xml}</parameter>"


def wonder_request_xml(year: int, age_var: str, age_values: list[str], title: str) -> str:
    params: list[str] = [parameter("accept_datause_restrictions", "true")]
    params.extend(
        parameter(name, value)
        for name, value in [
            ("B_1", "D158.V7"),
            ("B_2", "*None*"),
            ("B_3", "*None*"),
            ("B_4", "*None*"),
            ("B_5", "*None*"),
            ("M_1", "D158.M1"),
            ("M_2", "D158.M2"),
            ("M_3", "D158.M3"),
        ]
    )

    finder_defaults = [
        ("V1", str(year), f"{year} ({year})"),
        ("V2", "*All*", "*All* (All Causes of Death)"),
        ("V9", "*All*", "*All* (The United States)"),
        ("V10", "*All*", "*All* (The United States)"),
        ("V27", "*All*", "*All* (The United States)"),
        ("V30", "*All*", "*All* (The United States)"),
        ("V31", "*All*", "*All* (The United States)"),
    ]
    for field, value, label in finder_defaults:
        params.append(parameter(f"F_D158.{field}", value))
        params.append(parameter(f"I_D158.{field}", label))
        params.append(parameter(f"O_{field}_fmode", "freg"))

    filters: dict[str, str | list[str]] = {
        "V_D158.V1": "",
        "V_D158.V2": "",
        "V_D158.V9": "",
        "V_D158.V10": "",
        "V_D158.V27": "",
        "V_D158.V30": "",
        "V_D158.V31": "",
        "V_D158.V5": "*All*",
        "V_D158.V51": "*All*",
        "V_D158.V52": "*All*",
        "V_D158.V6": "00",
        "V_D158.V7": ["F", "M"],
        "V_D158.V17": "*All*",
        "V_D158.V42": "*All*",
        "V_D158.V43": "*All*",
        "V_D158.V44": "*All*",
        "V_D158.V45": "*All*",
        "V_D158.V11": "*All*",
        "V_D158.V18": "*All*",
        "V_D158.V19": "*All*",
        "V_D158.V20": "*All*",
        "V_D158.V21": "*All*",
        "V_D158.V22": "*All*",
        "V_D158.V23": "*All*",
        "V_D158.V24": "*All*",
        "V_D158.V25": "*All*",
        "V_D158.V28": "*All*",
        "V_D158.V29": "*All*",
        "V_D158.V4": "*All*",
        "V_D158.V12": "*All*",
    }
    filters[f"V_{age_var}"] = age_values
    params.extend(parameter(name, value) for name, value in filters.items())

    options = {
        "O_age": age_var,
        "O_ucd": "D158.V2",
        "O_location": "D158.V9",
        "O_race": "D158.V42",
        "O_urban": "D158.V19",
        "O_aar": "aar_none",
        "O_aar_pop": "0000",
        "O_javascript": "on",
        "O_show_totals": "true",
        "O_show_zeros": "false",
        "O_show_suppressed": "false",
        "O_precision": "1",
        "O_rate_per": "100000",
        "O_timeout": "600",
        "O_title": title,
        "action-Send": "Send",
        "stage": "request",
    }
    params.extend(parameter(name, value) for name, value in options.items())
    return '<?xml version="1.0" encoding="UTF-8"?><request-parameters>' + "".join(params) + "</request-parameters>"


def response_has_wonder_data(path: Path) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8", errors="replace").lstrip()
    if not text.startswith("<?xml"):
        return False
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return False
    return root.find(".//data-table") is not None


def request_wonder_xml(
    year: int,
    age_group: str,
    component: dict[str, object],
    min_interval: float,
    retry_wait: float,
    max_retries: int,
    last_request_time: list[float],
) -> Path:
    label = str(component["label"])
    out_path = RAW_WONDER_DIR / f"wonder_ucd_D158_{year}_{age_group.replace('+', 'plus')}_{label}.xml"
    request_path = RAW_WONDER_DIR / f"wonder_ucd_D158_{year}_{age_group.replace('+', 'plus')}_{label}_request.xml"
    if response_has_wonder_data(out_path):
        log(f"Using cached CDC WONDER response: {out_path.relative_to(PROJECT_ROOT)}")
        return out_path

    title = f"MSA burden US all-cause deaths {year} {age_group} by sex"
    request_xml = wonder_request_xml(year, str(component["age_var"]), list(component["values"]), title)
    request_path.write_text(request_xml + "\n", encoding="utf-8")

    for attempt in range(1, max_retries + 2):
        elapsed = time.time() - last_request_time[0]
        if last_request_time[0] > 0 and elapsed < min_interval:
            wait = min_interval - elapsed
            log(f"Waiting {wait:.0f}s before next CDC WONDER request.")
            time.sleep(wait)

        log(f"Requesting CDC WONDER {year} {age_group} component {label}, attempt {attempt}.")
        last_request_time[0] = time.time()
        try:
            response = requests.post(
                WONDER_ENDPOINT,
                data={"request_xml": request_xml, "accept_datause_restrictions": "true"},
                timeout=240,
            )
            out_path.write_text(response.text, encoding="utf-8")
            if response.status_code == 200 and response_has_wonder_data(out_path):
                return out_path
            reason = f"HTTP {response.status_code} {response.reason}"
        except requests.RequestException as exc:
            out_path.write_text(str(exc), encoding="utf-8")
            reason = str(exc)

        if attempt <= max_retries:
            log(f"CDC WONDER request failed for {age_group} {label}: {reason}. Retrying after {retry_wait:.0f}s.")
            time.sleep(retry_wait)
        else:
            stop(
                "CDC WONDER mortality download failed",
                f"Automatic CDC WONDER request failed for year {year}, age group {age_group}, component {label}. "
                f"Last error: {reason}. Raw response saved to `{out_path.relative_to(PROJECT_ROOT)}`. "
                "Manual download instructions were written.",
            )
    raise AssertionError("unreachable")


def parse_number(value: str | None) -> float:
    if value is None:
        return np.nan
    cleaned = re.sub(r"[^0-9.\-]", "", value)
    if cleaned == "":
        return np.nan
    return float(cleaned)


def parse_wonder_sex_rows(path: Path) -> pd.DataFrame:
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    table = root.find(".//data-table")
    if table is None:
        raise ValueError(f"No data-table in {path}")
    rows: list[dict[str, object]] = []
    for row in table.findall("r"):
        cells = list(row.findall("c"))
        if not cells:
            continue
        first = cells[0]
        if first.attrib.get("c") == "1" or "dt" in first.attrib:
            continue
        sex = first.attrib.get("l")
        if sex not in TARGET_SEXES or len(cells) < 3:
            continue
        rows.append(
            {
                "sex": sex,
                "deaths_allcause": parse_number(cells[1].attrib.get("v") or cells[1].attrib.get("dt")),
                "population": parse_number(cells[2].attrib.get("v") or cells[2].attrib.get("dt")),
            }
        )
    out = pd.DataFrame(rows)
    if set(out["sex"]) != set(TARGET_SEXES):
        raise ValueError(f"CDC WONDER response `{path}` did not contain both Female and Male rows.")
    return out


def write_mortality_manual_doc() -> None:
    MORTALITY_MANUAL_DOC.write_text(
        """# Manual CDC WONDER Mortality Download Instructions

Automatic CDC WONDER extraction did not complete. Do not fabricate death counts.

Use CDC WONDER: Underlying Cause of Death, 2018-2024, Single Race.

Required output: `data/external/us_allcause_deaths_by_age_sex.csv`

Required columns:

- `year`
- `sex`
- `age_group`
- `deaths_allcause`
- `population`
- `source`
- `notes`

Manual query:

1. Dataset: Underlying Cause of Death, 2018-2024, Single Race.
2. Geography: United States.
3. Year: latest final year available, preferably 2024 if final.
4. Cause of death: All Causes.
5. Sex: Female and Male.
6. Ages: aggregate exactly to 18-34, 35-44, 45-54, 55-64, 65-74, and 75+.
7. Export deaths and population.
8. Save to `data/external/us_allcause_deaths_by_age_sex.csv`.
""",
        encoding="utf-8",
    )


def build_mortality_file(args: argparse.Namespace) -> int:
    required = ["year", "sex", "age_group", "deaths_allcause", "population", "source", "notes"]
    if has_required_columns(DEATHS_FILE, required):
        log(f"Existing official mortality file found: {DEATHS_FILE.relative_to(PROJECT_ROOT)}")
        return int(pd.read_csv(DEATHS_FILE)["year"].dropna().astype(int).max())

    if args.skip_wonder:
        write_mortality_manual_doc()
        stop("CDC WONDER automatic download skipped", "Mortality file missing and `--skip-wonder` was set.")

    write_mortality_manual_doc()
    last_request_time = [0.0]
    for year in WONDER_YEAR_PREFERENCES:
        try:
            output_rows: list[dict[str, object]] = []
            for age_group in TARGET_AGE_GROUPS:
                component_rows = []
                component_labels = []
                for component in AGE_QUERY_COMPONENTS[age_group]:
                    xml_path = request_wonder_xml(
                        year=year,
                        age_group=age_group,
                        component=component,
                        min_interval=args.min_wonder_interval,
                        retry_wait=args.retry_wait,
                        max_retries=args.max_retries,
                        last_request_time=last_request_time,
                    )
                    component_rows.append(parse_wonder_sex_rows(xml_path))
                    component_labels.append(str(component["label"]))
                combined = pd.concat(component_rows, ignore_index=True).groupby("sex", as_index=False)[["deaths_allcause", "population"]].sum(min_count=1)
                for _, row in combined.iterrows():
                    output_rows.append(
                        {
                            "year": year,
                            "sex": row["sex"],
                            "age_group": age_group,
                            "deaths_allcause": int(round(float(row["deaths_allcause"]))),
                            "population": int(round(float(row["population"]))) if pd.notna(row["population"]) else np.nan,
                            "source": WONDER_SOURCE,
                            "notes": "All causes; United States; final mortality; components summed: " + ", ".join(component_labels),
                        }
                    )
            mortality = pd.DataFrame(output_rows)
            expected = {(age, sex) for age in TARGET_AGE_GROUPS for sex in TARGET_SEXES}
            found = set(zip(mortality["age_group"], mortality["sex"]))
            if found != expected:
                missing = sorted(expected - found)
                raise ValueError(f"Missing age-sex mortality strata: {missing}")
            mortality = mortality[required].sort_values(["age_group", "sex"]).reset_index(drop=True)
            mortality.to_csv(DEATHS_FILE, index=False)
            log(f"Created mortality file: {DEATHS_FILE.relative_to(PROJECT_ROOT)}")
            return year
        except SystemExit:
            raise
        except Exception as exc:
            log(f"Mortality download for {year} failed: {exc}")
            append_issue_once(
                f"CDC WONDER mortality download issue for {year}",
                f"The automatic CDC WONDER mortality extraction for {year} failed with: `{exc}`. "
                "The script will try the next final year if configured.",
            )
    stop(
        "Official mortality inputs missing",
        "Could not create `data/external/us_allcause_deaths_by_age_sex.csv` automatically. "
        f"Manual instructions are in `{MORTALITY_MANUAL_DOC.relative_to(PROJECT_ROOT)}`.",
    )
    raise AssertionError("unreachable")


def write_lifetable_manual_doc() -> None:
    LIFETABLE_MANUAL_DOC.write_text(
        """# Manual NCHS Life Table Download Instructions

Automatic NCHS life-table download did not complete. Do not fabricate life
expectancy values.

Preferred source: NCHS United States Life Tables, 2023, NVSR Volume 74, Number 6.

Required single-age output: `data/external/us_life_table_by_age_sex.csv`

Required columns:

- `year`
- `sex`
- `age`
- `remaining_life_expectancy`
- `source`
- `notes`

Then create `data/external/us_life_table_by_agegroup_sex.csv` using representative ages:

- 18-34: 25
- 35-44: 40
- 45-54: 50
- 55-64: 60
- 65-74: 70
- 75+: 80
""",
        encoding="utf-8",
    )


def download_life_table_workbooks() -> dict[str, Path]:
    write_lifetable_manual_doc()
    paths: dict[str, Path] = {}
    for sex, url in LIFE_TABLE_URLS.items():
        out_path = RAW_LIFE_DIR / Path(url).name
        if not out_path.exists():
            log(f"Downloading NCHS life table workbook for {sex}.")
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            out_path.write_bytes(response.content)
        paths[sex] = out_path
    return paths


def parse_life_age(label: object) -> int | None:
    if pd.isna(label):
        return None
    text = str(label).strip()
    if text.startswith("SOURCE"):
        return None
    if "older" in text:
        return 100
    match = re.match(r"^(\d+)", text)
    if not match:
        return None
    return int(match.group(1))


def build_life_table_files() -> int:
    required_single = ["year", "sex", "age", "remaining_life_expectancy", "source", "notes"]
    required_group = ["year", "sex", "age_group", "remaining_life_expectancy", "source", "notes"]
    if has_required_columns(LIFE_FILE, required_single) and has_required_columns(LIFE_GROUP_FILE, required_group):
        log("Existing official life-table files found.")
        return int(pd.read_csv(LIFE_GROUP_FILE)["year"].dropna().astype(int).max())

    paths = download_life_table_workbooks()
    rows: list[dict[str, object]] = []
    for sex, path in paths.items():
        df = pd.read_excel(path, header=None)
        for _, row in df.iterrows():
            age = parse_life_age(row.iloc[0])
            if age is None:
                continue
            ex = pd.to_numeric(row.iloc[6], errors="coerce")
            if pd.isna(ex):
                continue
            rows.append(
                {
                    "year": LIFE_TABLE_YEAR,
                    "sex": sex,
                    "age": age,
                    "remaining_life_expectancy": float(ex),
                    "source": LIFE_TABLE_SOURCE,
                    "notes": f"Downloaded from {path.name}; complete period life table.",
                }
            )
    life = pd.DataFrame(rows)
    if life.empty:
        stop("Life table parsing failed", "NCHS life table workbooks were downloaded but no usable rows were parsed.")
    life = life[required_single].sort_values(["sex", "age"]).reset_index(drop=True)
    life.to_csv(LIFE_FILE, index=False)

    group_rows: list[dict[str, object]] = []
    for sex in TARGET_SEXES:
        sex_life = life.loc[life["sex"] == sex].set_index("age")
        for age_group, rep_age in REPRESENTATIVE_AGES.items():
            if rep_age not in sex_life.index:
                stop("Life table representative age missing", f"Representative age {rep_age} was not found for {sex}.")
            group_rows.append(
                {
                    "year": LIFE_TABLE_YEAR,
                    "sex": sex,
                    "age_group": age_group,
                    "remaining_life_expectancy": float(sex_life.loc[rep_age, "remaining_life_expectancy"]),
                    "source": LIFE_TABLE_SOURCE,
                    "notes": f"Representative age method: {age_group} uses age {rep_age}; 75+ uses age 80.",
                }
            )
    group = pd.DataFrame(group_rows)[required_group].sort_values(["age_group", "sex"]).reset_index(drop=True)
    group.to_csv(LIFE_GROUP_FILE, index=False)
    log(f"Created life table files: {LIFE_FILE.relative_to(PROJECT_ROOT)}, {LIFE_GROUP_FILE.relative_to(PROJECT_ROOT)}")
    return LIFE_TABLE_YEAR


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-wonder", action="store_true", help="Do not call CDC WONDER; create manual instructions if mortality file is missing.")
    parser.add_argument("--min-wonder-interval", type=float, default=5.0, help="Minimum seconds between CDC WONDER requests.")
    parser.add_argument("--retry-wait", type=float, default=125.0, help="Seconds to wait after CDC WONDER 429/504 failures.")
    parser.add_argument("--max-retries", type=int, default=2, help="Retries per CDC WONDER component.")
    args = parser.parse_args()

    ensure_dirs()
    log("Starting external mortality/life-table preparation.")
    mortality_year = build_mortality_file(args)
    life_year = build_life_table_files()
    if mortality_year != life_year:
        append_issue_once(
            "Mortality and life-table years differ",
            f"All-cause deaths use final mortality year {mortality_year}, while remaining life expectancy uses NCHS United States Life Tables {life_year}. "
            "This is documented in burden outputs; update the life-table input when a matching final life table is available.",
        )
    log(f"External inputs ready. Mortality year: {mortality_year}; life table year: {life_year}.")


if __name__ == "__main__":
    main()
