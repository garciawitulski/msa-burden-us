"""Build NHIS 2024 current MSA prevalence dataset.

This script consumes either an IPUMS NHIS 2024 extract or the CDC/NCHS 2024
Sample Adult public-use file. It constructs current MSA prevalence variables
only; it does not estimate Cox models or burden deaths/YLL.
"""

from __future__ import annotations

import json
import zipfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data/raw/nhis_2024"
INTERIM_DIR = PROJECT_ROOT / "data/interim/nhis_2024"
PROCESSED_DIR = PROJECT_ROOT / "data/processed/nhis_2024"
LOG_DIR = PROJECT_ROOT / "outputs/logs"
TABLE_DIR = PROJECT_ROOT / "outputs/tables"

ISSUES = LOG_DIR / "issues_to_resolve.md"
MAPPING_REPORT = LOG_DIR / "nhis_2024_variable_mapping_report.md"
QC_REPORT = LOG_DIR / "nhis_2024_prevalence_quality_checks.md"
PROCESSED_CSV = PROCESSED_DIR / "nhis_2024_msa_prevalence_dataset.csv"
PROCESSED_DTA = PROCESSED_DIR / "nhis_2024_msa_prevalence_dataset.dta"

TABLE_OVERALL = TABLE_DIR / "nhis_2024_msa_prevalence_overall.csv"
TABLE_SEX = TABLE_DIR / "nhis_2024_msa_prevalence_by_sex.csv"
TABLE_AGE = TABLE_DIR / "nhis_2024_msa_prevalence_by_age.csv"
TABLE_AGE_SEX = TABLE_DIR / "nhis_2024_msa_prevalence_by_age_sex.csv"
TABLE_SOCIO = TABLE_DIR / "nhis_2024_msa_prevalence_by_sociodemographics.csv"
TABLE_PREMATURE_OVERALL = TABLE_DIR / "nhis_2024_msa_prevalence_premature_30_69_overall.csv"
TABLE_PREMATURE_SEX = TABLE_DIR / "nhis_2024_msa_prevalence_premature_30_69_by_sex.csv"
TABLE_PREMATURE_AGE = TABLE_DIR / "nhis_2024_msa_prevalence_premature_30_69_by_age.csv"
TABLE_PREMATURE_AGE_SEX = TABLE_DIR / "nhis_2024_msa_prevalence_premature_30_69_by_age_sex.csv"
TABLE_PREMATURE_SOCIO = TABLE_DIR / "nhis_2024_msa_prevalence_premature_30_69_by_sociodemographics.csv"


IPUMS_REQUIRED = ["YEAR", "SAMPWEIGHT", "AGE", "SEX", "STRONGFWK"]
CDC_REQUIRED = ["SRVY_YR", "WTFA_A", "AGEP_A", "SEX_A", "STRFREQW_A"]


def ensure_dirs() -> None:
    for path in [RAW_DIR, INTERIM_DIR, PROCESSED_DIR, LOG_DIR, TABLE_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def append_issue_once(title: str, message: str) -> None:
    ensure_dirs()
    old = ISSUES.read_text(encoding="utf-8") if ISSUES.exists() else "# Issues to Resolve\n\n"
    if title in old:
        return
    with ISSUES.open("w", encoding="utf-8") as handle:
        handle.write(old.rstrip() + "\n\n")
        handle.write(f"## {datetime.now().isoformat(timespec='seconds')} - {title}\n\n")
        handle.write(message.rstrip() + "\n")


def stop(title: str, message: str) -> None:
    append_issue_once(title, message)
    raise SystemExit(message)


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def first_existing(columns: list[str], candidates: list[str]) -> str | None:
    upper_map = {col.upper(): col for col in columns}
    for candidate in candidates:
        if candidate.upper() in upper_map:
            return upper_map[candidate.upper()]
    return None


def source_metadata() -> dict:
    path = INTERIM_DIR / "nhis_2024_download_metadata.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def csv_header_from_zip(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as zf:
        csv_names = [name for name in zf.namelist() if name.lower().endswith(".csv")]
        if not csv_names:
            return []
        with zf.open(csv_names[0]) as handle:
            return pd.read_csv(handle, nrows=0).columns.tolist()


def read_csv_from_zip(path: Path, usecols: list[str]) -> pd.DataFrame:
    with zipfile.ZipFile(path) as zf:
        csv_names = [name for name in zf.namelist() if name.lower().endswith(".csv")]
        if not csv_names:
            stop("CDC NHIS 2024 zip missing CSV", f"`{path}` does not contain a CSV file.")
        with zf.open(csv_names[0]) as handle:
            return pd.read_csv(handle, usecols=lambda col: col in usecols, low_memory=False)


def detect_input() -> tuple[str, Path, list[str]]:
    ipums_csvs = sorted(RAW_DIR.glob("*.csv.gz")) + sorted(RAW_DIR.glob("nhis_*.csv"))
    for path in ipums_csvs:
        header = pd.read_csv(path, nrows=0).columns.tolist()
        upper = {col.upper() for col in header}
        if all(col in upper for col in IPUMS_REQUIRED):
            return "ipums", path, header

    cdc_zips = sorted(RAW_DIR.glob("adult24csv.zip")) + sorted(RAW_DIR.glob("*adult*csv*.zip"))
    for path in cdc_zips:
        header = csv_header_from_zip(path)
        if all(col in header for col in CDC_REQUIRED):
            return "cdc", path, header

    cdc_csvs = sorted(RAW_DIR.glob("*adult*.csv"))
    for path in cdc_csvs:
        header = pd.read_csv(path, nrows=0).columns.tolist()
        if all(col in header for col in CDC_REQUIRED):
            return "cdc", path, header

    stop(
        "NHIS 2024 input not found",
        "No usable IPUMS or CDC NHIS 2024 Sample Adult file was found in `data/raw/nhis_2024/`. "
        "Run `python code/python/07_download_nhis_2024_prevalence.py` first.",
    )
    raise AssertionError("unreachable")


def load_source(source: str, path: Path, header: list[str]) -> pd.DataFrame:
    if source == "ipums":
        wanted = [
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
        cols = [first_existing(header, [col]) for col in wanted]
        usecols = [col for col in cols if col is not None]
        return pd.read_csv(path, usecols=usecols, low_memory=False)

    wanted = [
        "SRVY_YR",
        "HHX",
        "HHSTAT_A",
        "PSTRAT",
        "PPSU",
        "WTFA_A",
        "AGEP_A",
        "SEX_A",
        "HISPALLP_A",
        "EDUCP_A",
        "POVRATTC_A",
        "RATCAT_A",
        "REGION",
        "STRNR_A",
        "STRTPR_A",
        "STRFREQW_A",
        "PA18_05R_A",
    ]
    usecols = [col for col in wanted if col in header]
    if path.suffix.lower() == ".zip":
        return read_csv_from_zip(path, usecols)
    return pd.read_csv(path, usecols=usecols, low_memory=False)


def make_age_group(age: pd.Series) -> pd.Series:
    out = pd.Series(pd.NA, index=age.index, dtype="object")
    out.loc[age.between(18, 34, inclusive="both")] = "18-34"
    out.loc[age.between(35, 44, inclusive="both")] = "35-44"
    out.loc[age.between(45, 54, inclusive="both")] = "45-54"
    out.loc[age.between(55, 64, inclusive="both")] = "55-64"
    out.loc[age.between(65, 74, inclusive="both")] = "65-74"
    out.loc[age >= 75] = "75+"
    return out


def make_age_group_premature_30_69(age: pd.Series) -> pd.Series:
    out = pd.Series(pd.NA, index=age.index, dtype="object")
    out.loc[age.between(30, 34, inclusive="both")] = "30-34"
    out.loc[age.between(35, 44, inclusive="both")] = "35-44"
    out.loc[age.between(45, 54, inclusive="both")] = "45-54"
    out.loc[age.between(55, 64, inclusive="both")] = "55-64"
    out.loc[age.between(65, 69, inclusive="both")] = "65-69"
    return out


def sex_label(values: pd.Series) -> pd.Series:
    labels = {1: "Male", 2: "Female"}
    return values.map(labels).astype("object")


def region_label(values: pd.Series) -> pd.Series:
    labels = {1: "Northeast", 2: "Midwest", 3: "South", 4: "West"}
    return values.map(labels).astype("object")


def ipums_race_ethnicity(df: pd.DataFrame) -> pd.Series:
    race = numeric(df["RACEA"]) if "RACEA" in df else pd.Series(np.nan, index=df.index)
    hisp = numeric(df["HISPETH"]) if "HISPETH" in df else pd.Series(np.nan, index=df.index)
    out = pd.Series(pd.NA, index=df.index, dtype="object")
    out.loc[hisp.between(20, 70, inclusive="both")] = "Hispanic"
    non_hisp = hisp == 10
    out.loc[non_hisp & (race == 100)] = "Non-Hispanic White"
    out.loc[non_hisp & (race == 200)] = "Non-Hispanic Black"
    out.loc[non_hisp & race.between(300, 399, inclusive="both")] = "Non-Hispanic American Indian/Alaska Native"
    out.loc[non_hisp & race.between(400, 499, inclusive="both")] = "Non-Hispanic Asian/Pacific Islander"
    out.loc[non_hisp & race.between(500, 599, inclusive="both")] = "Non-Hispanic Other race"
    out.loc[non_hisp & race.between(600, 699, inclusive="both")] = "Non-Hispanic Multiple race"
    return out


def cdc_race_ethnicity(values: pd.Series) -> pd.Series:
    labels = {
        1: "Hispanic",
        2: "Non-Hispanic White",
        3: "Non-Hispanic Black",
        4: "Non-Hispanic Asian",
        5: "Non-Hispanic AIAN",
        6: "Non-Hispanic AIAN and any other group",
        7: "Other single and multiple races",
    }
    return values.map(labels).astype("object")


def ipums_education(values: pd.Series) -> pd.Series:
    out = pd.Series(pd.NA, index=values.index, dtype="object")
    out.loc[values.between(100, 199, inclusive="both")] = "Less than high school"
    out.loc[values.between(200, 299, inclusive="both")] = "High school/GED"
    out.loc[values.between(300, 399, inclusive="both")] = "Some college/AA"
    out.loc[values.between(400, 499, inclusive="both")] = "Bachelor's degree"
    out.loc[values.between(500, 599, inclusive="both")] = "Graduate/professional degree"
    return out


def cdc_education(values: pd.Series) -> pd.Series:
    out = pd.Series(pd.NA, index=values.index, dtype="object")
    out.loc[values.isin([0, 1, 2])] = "Less than high school"
    out.loc[values.isin([3, 4])] = "High school/GED"
    out.loc[values.isin([5, 6, 7])] = "Some college/AA"
    out.loc[values == 8] = "Bachelor's degree"
    out.loc[values.isin([9, 10])] = "Graduate/professional degree"
    return out


def ipums_poverty(values: pd.Series) -> pd.Series:
    out = pd.Series(pd.NA, index=values.index, dtype="object")
    out.loc[values.between(10, 14, inclusive="both")] = "<1.00 poverty ratio"
    out.loc[values.between(20, 25, inclusive="both")] = "1.00-1.99 poverty ratio"
    out.loc[values.between(30, 38, inclusive="both")] = ">=2.00 poverty ratio"
    return out


def cdc_poverty_from_ratio(values: pd.Series) -> pd.Series:
    out = pd.Series(pd.NA, index=values.index, dtype="object")
    out.loc[values < 1] = "<1.00 poverty ratio"
    out.loc[(values >= 1) & (values < 2)] = "1.00-1.99 poverty ratio"
    out.loc[values >= 2] = ">=2.00 poverty ratio"
    return out


def cdc_poverty_from_ratcat(values: pd.Series) -> pd.Series:
    out = pd.Series(pd.NA, index=values.index, dtype="object")
    out.loc[values.between(1, 3, inclusive="both")] = "<1.00 poverty ratio"
    out.loc[values.between(4, 7, inclusive="both")] = "1.00-1.99 poverty ratio"
    out.loc[values.between(8, 14, inclusive="both")] = ">=2.00 poverty ratio"
    return out


def clean_strongfwk_ipums(values: pd.Series) -> pd.Series:
    raw = numeric(values)
    out = pd.Series(np.nan, index=values.index, dtype="float64")
    out.loc[raw == 95] = 0.0
    out.loc[raw == 94] = 0.5
    valid = raw.between(1, 92, inclusive="both")
    out.loc[valid] = raw.loc[valid]
    return out


def clean_strfreqw_cdc(values: pd.Series) -> pd.Series:
    raw = numeric(values)
    out = pd.Series(np.nan, index=values.index, dtype="float64")
    out.loc[raw == 94] = 0.0
    out.loc[raw == 0] = 0.5
    valid = raw.between(1, 28, inclusive="both")
    out.loc[valid] = raw.loc[valid]
    return out


def pa18_combined(values: pd.Series) -> pd.Series:
    labels = {1: "neither guideline", 2: "MSA only", 3: "aerobic only", 4: "both guidelines"}
    return values.map(labels).astype("object")


def construct_ipums(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    age = numeric(df["AGE"])
    strong = clean_strongfwk_ipums(df["STRONGFWK"])
    out = pd.DataFrame(
        {
            "source": "ipums",
            "survey_year": numeric(df["YEAR"]).astype("Int64"),
            "person_id": df["NHISPID"].astype(str) if "NHISPID" in df else df.get("SERIAL", pd.Series(range(len(df)))).astype(str),
            "sample_adult": numeric(df["ASTATFLG"]).eq(1).astype("Int64") if "ASTATFLG" in df else 1,
            "weight_sample_adult": numeric(df["SAMPWEIGHT"]),
            "strata": numeric(df["STRATA"]) if "STRATA" in df else np.nan,
            "psu": numeric(df["PSU"]) if "PSU" in df else np.nan,
            "age": age,
            "age_group": make_age_group(age),
            "sex": sex_label(numeric(df["SEX"])),
            "race_ethnicity": ipums_race_ethnicity(df),
            "education": ipums_education(numeric(df["EDUC"])) if "EDUC" in df else pd.NA,
            "poverty": ipums_poverty(numeric(df["POVERTY"])) if "POVERTY" in df else pd.NA,
            "region": region_label(numeric(df["REGION"])) if "REGION" in df else pd.NA,
            "msa_times_week_2024": strong,
            "src_strength_frequency": numeric(df["STRONGFWK"]),
        }
    )
    if "PA18AERSTR" in df:
        pa18 = numeric(df["PA18AERSTR"])
        out["combined_pa_guideline_2024"] = pa18_combined(pa18)
        out["aerobic_guideline_2024"] = pd.Series(np.where(pa18.isin([3, 4]), 1, np.where(pa18.isin([1, 2]), 0, np.nan)), index=df.index)
        out["src_pa18aerstr"] = pa18
    else:
        out["combined_pa_guideline_2024"] = pd.NA
        out["aerobic_guideline_2024"] = np.nan
    mapping = {
        "strength_frequency": "STRONGFWK",
        "weight": "SAMPWEIGHT",
        "age": "AGE",
        "sex": "SEX",
        "combined_guideline": "PA18AERSTR if present",
    }
    return finalize_constructed(out), mapping


def construct_cdc(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    age = numeric(df["AGEP_A"])
    strong = clean_strfreqw_cdc(df["STRFREQW_A"])
    poverty = cdc_poverty_from_ratio(numeric(df["POVRATTC_A"])) if "POVRATTC_A" in df else cdc_poverty_from_ratcat(numeric(df["RATCAT_A"]))
    out = pd.DataFrame(
        {
            "source": "cdc",
            "survey_year": numeric(df["SRVY_YR"]).astype("Int64"),
            "person_id": df["HHX"].astype(str) if "HHX" in df else pd.Series(range(len(df))).astype(str),
            "sample_adult": numeric(df["HHSTAT_A"]).eq(1).astype("Int64") if "HHSTAT_A" in df else 1,
            "weight_sample_adult": numeric(df["WTFA_A"]),
            "strata": numeric(df["PSTRAT"]) if "PSTRAT" in df else np.nan,
            "psu": numeric(df["PPSU"]) if "PPSU" in df else np.nan,
            "age": age,
            "age_group": make_age_group(age),
            "sex": sex_label(numeric(df["SEX_A"])),
            "race_ethnicity": cdc_race_ethnicity(numeric(df["HISPALLP_A"])) if "HISPALLP_A" in df else pd.NA,
            "education": cdc_education(numeric(df["EDUCP_A"])) if "EDUCP_A" in df else pd.NA,
            "poverty": poverty,
            "region": region_label(numeric(df["REGION"])) if "REGION" in df else pd.NA,
            "msa_times_week_2024": strong,
            "src_strength_frequency": numeric(df["STRFREQW_A"]),
        }
    )
    if "PA18_05R_A" in df:
        pa18 = numeric(df["PA18_05R_A"])
        out["combined_pa_guideline_2024"] = pa18_combined(pa18)
        out["aerobic_guideline_2024"] = pd.Series(np.where(pa18.isin([3, 4]), 1, np.where(pa18.isin([1, 2]), 0, np.nan)), index=df.index)
        out["src_pa18_guideline"] = pa18
    else:
        out["combined_pa_guideline_2024"] = pd.NA
        out["aerobic_guideline_2024"] = np.nan
    mapping = {
        "strength_frequency": "STRFREQW_A",
        "weight": "WTFA_A",
        "age": "AGEP_A",
        "sex": "SEX_A",
        "combined_guideline": "PA18_05R_A if present",
    }
    return finalize_constructed(out), mapping


def finalize_constructed(out: pd.DataFrame) -> pd.DataFrame:
    out["msa_guideline_2024"] = np.where(out["msa_times_week_2024"] >= 2, 1, np.where(out["msa_times_week_2024"].notna(), 0, np.nan))
    out["insufficient_msa_2024"] = np.where(out["msa_times_week_2024"] < 2, 1, np.where(out["msa_times_week_2024"].notna(), 0, np.nan))
    out["nonmissing_msa_2024"] = out["msa_times_week_2024"].notna().astype(int)
    out["adult_18plus"] = (out["age"] >= 18).astype("Int64")
    out["adult_30_69"] = out["age"].between(30, 69, inclusive="both").astype("Int64")
    out["age_group_premature_30_69"] = make_age_group_premature_30_69(out["age"])
    return out


def weighted_prevalence(df: pd.DataFrame, group_cols: list[str], table_name: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    groups = [((), df)] if not group_cols else df.dropna(subset=group_cols).groupby(group_cols, dropna=True, sort=True)
    for key, sub in groups:
        if group_cols and not isinstance(key, tuple):
            key = (key,)
        weights = numeric(sub["weight_sample_adult"])
        valid = weights.notna() & (weights > 0) & sub["insufficient_msa_2024"].notna()
        analysis = sub.loc[valid]
        weights = weights.loc[valid]
        meets = numeric(analysis["msa_guideline_2024"])
        insufficient = numeric(analysis["insufficient_msa_2024"])
        row = {
            "table": table_name,
            "n_unweighted": int(len(analysis)),
            "weighted_total": float(weights.sum()),
            "weighted_meets_msa_guideline": float((weights * meets).sum()),
            "weighted_insufficient_msa": float((weights * insufficient).sum()),
            "prevalence_meets_msa_guideline": float((weights * meets).sum() / weights.sum()) if weights.sum() > 0 else np.nan,
            "prevalence_insufficient_msa": float((weights * insufficient).sum() / weights.sum()) if weights.sum() > 0 else np.nan,
        }
        if not group_cols:
            row.update({"group": "overall", "group_value": "all"})
        else:
            row.update({col: value for col, value in zip(group_cols, key)})
        rows.append(row)
    return pd.DataFrame(rows)


def write_tables(out: pd.DataFrame) -> dict[str, pd.DataFrame]:
    eligible = out.loc[(out["adult_18plus"] == 1) & (out["sample_adult"] == 1)].copy()
    tables = {
        "overall": weighted_prevalence(eligible, [], "overall"),
        "sex": weighted_prevalence(eligible, ["sex"], "sex"),
        "age": weighted_prevalence(eligible, ["age_group"], "age_group"),
        "age_sex": weighted_prevalence(eligible, ["age_group", "sex"], "age_group_sex"),
    }
    socio_frames = []
    for var in ["race_ethnicity", "education", "poverty", "region"]:
        if var in eligible and eligible[var].notna().any():
            frame = weighted_prevalence(eligible, [var], var)
            frame = frame.rename(columns={var: "group_value"})
            frame.insert(1, "sociodemographic_variable", var)
            socio_frames.append(frame)
    tables["sociodemographics"] = pd.concat(socio_frames, ignore_index=True) if socio_frames else pd.DataFrame()
    tables["overall"].to_csv(TABLE_OVERALL, index=False)
    tables["sex"].to_csv(TABLE_SEX, index=False)
    tables["age"].to_csv(TABLE_AGE, index=False)
    tables["age_sex"].to_csv(TABLE_AGE_SEX, index=False)
    tables["sociodemographics"].to_csv(TABLE_SOCIO, index=False)
    return tables


def write_premature_30_69_tables(out: pd.DataFrame) -> dict[str, pd.DataFrame]:
    eligible = out.loc[
        (out["adult_30_69"] == 1)
        & (out["sample_adult"] == 1)
        & out["age_group_premature_30_69"].notna()
    ].copy()
    eligible = eligible.rename(columns={"age_group": "age_group_18plus", "age_group_premature_30_69": "age_group"})
    tables = {
        "overall": weighted_prevalence(eligible, [], "premature_30_69_overall"),
        "sex": weighted_prevalence(eligible, ["sex"], "premature_30_69_sex"),
        "age": weighted_prevalence(eligible, ["age_group"], "premature_30_69_age_group"),
        "age_sex": weighted_prevalence(eligible, ["age_group", "sex"], "premature_30_69_age_group_sex"),
    }
    socio_frames = []
    for var in ["race_ethnicity", "education", "poverty", "region"]:
        if var in eligible and eligible[var].notna().any():
            frame = weighted_prevalence(eligible, [var], f"premature_30_69_{var}")
            frame = frame.rename(columns={var: "group_value"})
            frame.insert(1, "sociodemographic_variable", var)
            socio_frames.append(frame)
    tables["sociodemographics"] = pd.concat(socio_frames, ignore_index=True) if socio_frames else pd.DataFrame()
    for frame in tables.values():
        if not frame.empty:
            frame.insert(0, "analysis_population", "premature_30_69")
            frame.insert(1, "age_range", "30-69")
            frame.insert(2, "denominator", "NHIS 2024 sample adults aged 30-69 with nonmissing MSA and positive sample adult weight")
            frame.insert(3, "weight", "weight_sample_adult")
    tables["overall"].to_csv(TABLE_PREMATURE_OVERALL, index=False)
    tables["sex"].to_csv(TABLE_PREMATURE_SEX, index=False)
    tables["age"].to_csv(TABLE_PREMATURE_AGE, index=False)
    tables["age_sex"].to_csv(TABLE_PREMATURE_AGE_SEX, index=False)
    tables["sociodemographics"].to_csv(TABLE_PREMATURE_SOCIO, index=False)
    return tables


def write_mapping_report(source: str, path: Path, header: list[str], mapping: dict[str, str], metadata: dict) -> None:
    metadata_files = sorted(p.name for p in RAW_DIR.glob("*") if p.suffix.lower() in {".xml", ".pdf", ".cbk", ".sts", ".json"})
    MAPPING_REPORT.write_text(
        f"""# NHIS 2024 Variable Mapping Report

Generated: {datetime.now().isoformat(timespec="seconds")}

## Source detected

- Source: `{source}`
- Data file: `{path.relative_to(PROJECT_ROOT)}`
- Metadata/codebook files found: {", ".join(metadata_files) if metadata_files else "none"}
- Download metadata source: `{metadata.get("source", "unknown")}`

## Variable mapping

| Construct | Source variable |
|---|---|
| Survey year | {mapping.get("year", "YEAR or SRVY_YR")} |
| Person identifier | `NHISPID`/`HHX` depending on source |
| Sample adult flag | `ASTATFLG` if IPUMS; `HHSTAT_A` if CDC |
| Sample adult weight | {mapping["weight"]} |
| Strata | `STRATA` if IPUMS; `PSTRAT` if CDC |
| PSU | `PSU` if IPUMS; `PPSU` if CDC |
| MSA frequency | {mapping["strength_frequency"]} |
| Age | {mapping["age"]} |
| Sex | {mapping["sex"]} |
| Combined aerobic/strength guideline | {mapping["combined_guideline"]} |

## Coding decisions

- IPUMS `STRONGFWK`: 95 never = 0 times/week; 94 less than once/week = 0.5; 1-92 retained; 00, 93, 96, 97, 98, and 99 set missing.
- CDC `STRFREQW_A`: 94 never = 0 times/week; 00 less than once/week = 0.5; 1-28 retained; 95, 96, 97, 98, and 99 set missing after inspecting the 2024 Sample Adult codebook.
- `msa_guideline_2024` = 1 if MSA frequency >= 2 times/week, 0 if frequency is nonmissing and <2.
- `insufficient_msa_2024` = 1 if MSA frequency is nonmissing and <2 times/week, 0 if >=2.
- Prevalence uses the sample adult survey weight, not a mortality weight.

## Premature mortality prevalence outputs

The `premature_30_69` prevalence outputs are restricted to NHIS 2024 sample
adults aged 30-69 with nonmissing MSA and positive sample adult weight. Exact
age groups are 30-34, 35-44, 45-54, 55-64, and 65-69. These outputs are intended
for the WHO-style premature mortality burden analysis and do not replace the
previous all-adult 18+ prevalence files.

## Columns found

{", ".join(header)}
""",
        encoding="utf-8",
    )


def write_qc_report(out: pd.DataFrame, tables: dict[str, pd.DataFrame], source: str, path: Path) -> None:
    overall = tables["overall"].iloc[0]
    premature_rows = int(((out["adult_30_69"] == 1) & (out["sample_adult"] == 1)).sum())
    premature_nonmissing = int(((out["adult_30_69"] == 1) & (out["sample_adult"] == 1) & out["msa_times_week_2024"].notna()).sum())
    missing_msa = int(out["msa_times_week_2024"].isna().sum())
    QC_REPORT.write_text(
        f"""# NHIS 2024 Prevalence Quality Checks

Generated: {datetime.now().isoformat(timespec="seconds")}

- Source: `{source}`
- Data file: `{path.relative_to(PROJECT_ROOT)}`
- Processed rows: {len(out):,}
- Adult 18+ sample rows: {int(((out["adult_18plus"] == 1) & (out["sample_adult"] == 1)).sum()):,}
- Nonmissing MSA rows: {int(out["nonmissing_msa_2024"].sum()):,}
- Missing MSA rows: {missing_msa:,}
- Adult 30-69 sample rows: {premature_rows:,}
- Adult 30-69 sample rows with nonmissing MSA: {premature_nonmissing:,}
- Overall weighted prevalence meeting MSA guideline: {float(overall["prevalence_meets_msa_guideline"]):.4f}
- Overall weighted prevalence insufficient MSA: {float(overall["prevalence_insufficient_msa"]):.4f}
- Weight used: `weight_sample_adult`
- Premature 30-69 outputs use exact age groups 30-34, 35-44, 45-54, 55-64, and 65-69.

No Cox models, attributable deaths, YLL, life expectancy gains, or productivity
losses were estimated in this script.
""",
        encoding="utf-8",
    )


def main() -> None:
    ensure_dirs()
    source, path, header = detect_input()
    metadata = source_metadata()
    df = load_source(source, path, header)
    if source == "ipums":
        out, mapping = construct_ipums(df)
    else:
        out, mapping = construct_cdc(df)

    eligible = out.loc[(out["adult_18plus"] == 1) & (out["sample_adult"] == 1)]
    if eligible["weight_sample_adult"].isna().all() or (numeric(eligible["weight_sample_adult"]) <= 0).all():
        stop("NHIS 2024 prevalence weight unavailable", "No positive sample adult survey weights were available for NHIS 2024 prevalence.")
    if eligible["insufficient_msa_2024"].notna().sum() == 0:
        stop("NHIS 2024 MSA unavailable", "No nonmissing 2024 MSA frequency values were available after coding missing values.")

    out.to_csv(PROCESSED_CSV, index=False)
    try:
        out.to_stata(PROCESSED_DTA, write_index=False, version=118)
    except Exception as error:
        append_issue_once(
            "NHIS 2024 Stata export failed",
            f"`{PROCESSED_DTA}` could not be written. CSV output was created. Error: {error}",
        )

    tables = write_tables(out)
    premature_tables = write_premature_30_69_tables(out)
    write_mapping_report(source, path, header, mapping, metadata)
    write_qc_report(out, tables, source, path)
    print(f"Built NHIS 2024 MSA prevalence dataset from {source}: {PROCESSED_CSV.relative_to(PROJECT_ROOT)}")
    print(f"Overall insufficient MSA prevalence: {float(tables['overall'].iloc[0]['prevalence_insufficient_msa']):.4f}")
    print(f"Premature 30-69 insufficient MSA prevalence: {float(premature_tables['overall'].iloc[0]['prevalence_insufficient_msa']):.4f}")


if __name__ == "__main__":
    main()
