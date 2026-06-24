"""Build regression-ready NHIS linked mortality datasets for MSA analyses."""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyreadstat


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data/raw"
INTERIM_DIR = PROJECT_ROOT / "data/interim"
PROCESSED_DIR = PROJECT_ROOT / "data/processed"
LOG_DIR = PROJECT_ROOT / "outputs/logs"
TABLE_DIR = PROJECT_ROOT / "outputs/tables"

LMF_CENSOR_YEAR = 2019
LMF_CENSOR_QUARTER = 4

FOLLOWUP_CANDIDATES = ["PERMTH_INT", "PERMTH_EXM", "PERMTH", "FOLLOWUP_MONTHS"]

REQUIRED_SOURCES = [
    "YEAR",
    "QUARTER",
    "NHISPID",
    "ASTATFLG",
    "AGE",
    "MORTELIG",
    "MORTSTAT",
    "MORTDODY",
    "MORTDODQ",
    "MORTWTSA",
    "STRONGFWK",
]

SOURCE_KEEPERS = [
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
    "MORTELIG",
    "MORTSTAT",
    "MORTDODY",
    "MORTDODQ",
    "MORTUCODLD",
    "MORTUCOD",
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
    "AGE",
    "SEX",
    "RACEA",
    "HISPETH",
    "EDUC",
    "POVERTY",
    "MARSTAT",
    "REGION",
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

COMPLETE_CASE_VARS = [
    "adult_18plus",
    "sample_adult",
    "mortality_linkage_eligible",
    "nonmissing_followup",
    "nonmissing_msa",
    "followup_time_months",
    "followup_time_years",
    "died_allcause",
    "msa_days_week",
    "msa_cat5",
    "msa_guideline",
    "aerobic_minutes_meq_weekly",
    "aerobic_meets_guideline",
    "age",
    "sex",
    "race_ethnicity",
    "education",
    "poverty",
    "marital_status",
    "region",
    "bmi",
    "smoking_status",
    "alcohol_use",
    "self_rated_health",
    "diabetes",
    "hypertension",
    "cvd_history",
    "cancer_history",
    "weight_mortality",
    "strata",
    "psu",
]

MISSING_TERMS = [
    "niu",
    "unknown",
    "refused",
    "not ascertained",
    "don't know",
    "undefinable",
]

VALUE_LABELS_FOR_DTA = {
    "msa_cat5": {
        0: "0 days/week",
        1: "1 day/week",
        2: "2 days/week",
        3: "3-4 days/week",
        4: "5+ days/week",
    },
    "msa_guideline": {0: "Does not meet MSA guideline", 1: "Meets MSA guideline"},
    "insufficient_msa": {0: "Meets MSA guideline", 1: "Insufficient MSA"},
    "died_allcause": {0: "Assumed alive", 1: "Assumed deceased"},
    "mortality_linkage_eligible": {0: "Not eligible", 1: "Eligible"},
    "sample_adult": {0: "Not sample adult with record", 1: "Sample adult with record"},
    "adult_18plus": {0: "Under 18", 1: "Age 18+"},
    "adult_20plus": {0: "Under 20", 1: "Age 20+"},
    "complete_case_main": {0: "Not complete case", 1: "Complete case"},
    "complete_case_lag24": {0: "Not lag24 analytic case", 1: "Lag24 analytic case"},
}


def ensure_dirs() -> None:
    for path in [INTERIM_DIR, PROCESSED_DIR, LOG_DIR, TABLE_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def write_issue(message: str) -> None:
    ensure_dirs()
    path = LOG_DIR / "issues_to_resolve.md"
    old = path.read_text(encoding="utf-8") if path.exists() else "# Issues to Resolve\n\n"
    with path.open("w", encoding="utf-8") as handle:
        handle.write(old.rstrip() + "\n\n")
        handle.write(f"## {datetime.now().isoformat(timespec='seconds')}\n\n")
        handle.write(message.rstrip() + "\n")


def write_issue_once(message: str) -> None:
    ensure_dirs()
    path = LOG_DIR / "issues_to_resolve.md"
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    if message.rstrip() in old:
        return
    write_issue(message)


def stop(message: str) -> None:
    write_issue(message)
    raise SystemExit(message)


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.rename(columns={col: str(col).upper() for col in df.columns})
    duplicates = out.columns[out.columns.duplicated()].tolist()
    if duplicates:
        stop(f"Duplicate column names after upper-case normalization: {duplicates}")
    return out


def find_data_file() -> Path:
    candidates: list[Path] = []
    for pattern in ["*.dta", "*.csv", "*.csv.gz"]:
        candidates.extend(RAW_DIR.glob(pattern))
    candidates = sorted(p for p in candidates if p.is_file())
    if not candidates:
        stop("No supported raw IPUMS data file found in `data/raw/`.")
    return candidates[0]


def node_text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return " ".join("".join(node.itertext()).split())


def parse_ddi_xml(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, str], dict[str, dict[Any, str]]]:
    variable_info: dict[str, dict[str, Any]] = {}
    variable_labels: dict[str, str] = {}
    value_labels: dict[str, dict[Any, str]] = {}
    root = ET.parse(path).getroot()
    for var in root.findall(".//{*}var"):
        name = (var.attrib.get("name") or var.attrib.get("ID") or "").upper()
        if not name:
            continue
        label = node_text(var.find("{*}labl"))
        text = node_text(var.find("{*}txt"))
        cod_instr = node_text(var.find("{*}codInstr"))
        variable_info[name] = {
            "label": label,
            "text": text,
            "cod_instr": cod_instr,
            "dcml": var.attrib.get("dcml", ""),
            "intrvl": var.attrib.get("intrvl", ""),
        }
        if label:
            variable_labels[name] = label
        labels: dict[Any, str] = {}
        for cat in var.findall("{*}catgry"):
            cat_value = cat.find("{*}catValu")
            cat_label = cat.find("{*}labl")
            if cat_value is None or cat_label is None:
                continue
            raw_key = node_text(cat_value)
            raw_label = node_text(cat_label)
            if raw_key == "":
                continue
            labels[raw_key] = raw_label
            try:
                labels[int(raw_key)] = raw_label
            except ValueError:
                try:
                    labels[float(raw_key)] = raw_label
                except ValueError:
                    pass
        if labels:
            value_labels[name] = labels
    return variable_info, variable_labels, value_labels


def read_data_and_metadata(path: Path) -> tuple[pd.DataFrame, dict[str, dict[str, Any]], dict[str, str], dict[str, dict[Any, str]]]:
    suffixes = "".join(path.suffixes).lower()
    variable_info: dict[str, dict[str, Any]] = {}
    variable_labels: dict[str, str] = {}
    value_labels: dict[str, dict[Any, str]] = {}

    if path.suffix.lower() == ".dta":
        df, meta = pyreadstat.read_dta(path, apply_value_formats=False)
        df = normalize_columns(df)
        variable_labels = {k.upper(): v for k, v in zip(meta.column_names, meta.column_labels) if v}
        value_labels = {k.upper(): v for k, v in meta.variable_value_labels.items()}
        variable_info = {name: {"label": label, "text": "", "cod_instr": ""} for name, label in variable_labels.items()}
        return df, variable_info, variable_labels, value_labels

    if suffixes.endswith(".csv") or suffixes.endswith(".csv.gz"):
        dtype = {
            "NHISPID": "string",
            "NHISHID": "string",
            "HHX": "string",
            "FMX": "string",
            "PX": "string",
        }
        df = pd.read_csv(path, low_memory=False, dtype=dtype)
        df = normalize_columns(df)
        xml_files = sorted(RAW_DIR.glob("*.xml"))
        if not xml_files:
            stop("CSV data were found, but no DDI XML codebook was found in `data/raw/`.")
        variable_info, variable_labels, value_labels = parse_ddi_xml(xml_files[0])
        return df, variable_info, variable_labels, value_labels

    stop(f"Unsupported data file format: {path.name}")


def numeric(df: pd.DataFrame, var: str) -> pd.Series:
    if var not in df:
        return pd.Series(np.nan, index=df.index, dtype="float64")
    return pd.to_numeric(df[var], errors="coerce")


def get_label(labels: dict[Any, str], value: Any) -> str | None:
    if pd.isna(value):
        return None
    keys: list[Any] = [value, str(value)]
    try:
        numeric_value = float(value)
        if numeric_value.is_integer():
            keys.extend([int(numeric_value), str(int(numeric_value)), f"{int(numeric_value):02d}", f"{int(numeric_value):03d}"])
        keys.append(numeric_value)
    except (TypeError, ValueError):
        pass
    for key in keys:
        if key in labels:
            return labels[key]
    return None


def decode(df: pd.DataFrame, var: str, value_labels: dict[str, dict[Any, str]]) -> pd.Series:
    if var not in df:
        return pd.Series(pd.NA, index=df.index, dtype="object")
    labels = value_labels.get(var, {})
    if not labels:
        return df[var].astype("string")
    return df[var].map(lambda value: get_label(labels, value) if get_label(labels, value) is not None else pd.NA)


def clean_decoded(df: pd.DataFrame, var: str, value_labels: dict[str, dict[Any, str]]) -> pd.Series:
    out = decode(df, var, value_labels).astype("object")
    text = out.astype("string").str.lower()
    missing = pd.Series(False, index=df.index)
    for term in MISSING_TERMS:
        missing = missing | text.str.contains(term, regex=False, na=False)
    out.loc[missing] = pd.NA
    return out


def recode_weekly_frequency(df: pd.DataFrame, var: str) -> pd.Series:
    values = numeric(df, var)
    out = pd.Series(np.nan, index=df.index, dtype="float64")
    out.loc[values.between(1, 92, inclusive="both")] = values.loc[values.between(1, 92, inclusive="both")]
    out.loc[values == 94] = 0.5
    out.loc[values == 95] = 0.0
    return out


def recode_duration_minutes(df: pd.DataFrame, var: str, weekly_frequency: pd.Series) -> pd.Series:
    values = numeric(df, var)
    out = pd.Series(np.nan, index=df.index, dtype="float64")
    out.loc[values.between(1, 995, inclusive="both")] = values.loc[values.between(1, 995, inclusive="both")]
    out.loc[weekly_frequency == 0] = 0.0
    return out


def make_msa_category(msa_days_week: pd.Series) -> pd.Series:
    out = pd.Series(np.nan, index=msa_days_week.index, dtype="float64")
    out.loc[msa_days_week.notna() & (msa_days_week < 1)] = 0
    out.loc[msa_days_week == 1] = 1
    out.loc[msa_days_week == 2] = 2
    out.loc[msa_days_week.between(3, 4, inclusive="both")] = 3
    out.loc[msa_days_week >= 5] = 4
    return out


def msa_category_label(msa_cat5: pd.Series) -> pd.Series:
    labels = VALUE_LABELS_FOR_DTA["msa_cat5"]
    return msa_cat5.map(labels).astype("object")


def make_aerobic_category(minutes: pd.Series) -> pd.Series:
    out = pd.Series(pd.NA, index=minutes.index, dtype="object")
    out.loc[minutes == 0] = "inactive"
    out.loc[(minutes > 0) & (minutes < 150)] = "insufficiently active"
    out.loc[minutes >= 150] = "meets guideline"
    return out


def binary_from_codes(df: pd.DataFrame, var: str, yes_codes: list[int], no_codes: list[int]) -> pd.Series:
    values = numeric(df, var)
    out = pd.Series(np.nan, index=df.index, dtype="float64")
    out.loc[values.isin(no_codes)] = 0.0
    out.loc[values.isin(yes_codes)] = 1.0
    return out


def race_ethnicity(df: pd.DataFrame) -> pd.Series:
    race = numeric(df, "RACEA")
    hisp = numeric(df, "HISPETH")
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


def education_category(df: pd.DataFrame) -> pd.Series:
    educ = numeric(df, "EDUC")
    out = pd.Series(pd.NA, index=df.index, dtype="object")
    out.loc[educ.between(100, 199, inclusive="both")] = "Less than high school"
    out.loc[educ.between(200, 299, inclusive="both")] = "High school/GED"
    out.loc[educ.between(300, 399, inclusive="both")] = "Some college/AA"
    out.loc[educ.between(400, 499, inclusive="both")] = "Bachelor's degree"
    out.loc[educ.between(500, 599, inclusive="both")] = "Graduate/professional degree"
    return out


def poverty_category(df: pd.DataFrame) -> pd.Series:
    poverty = numeric(df, "POVERTY")
    out = pd.Series(pd.NA, index=df.index, dtype="object")
    out.loc[poverty.between(10, 14, inclusive="both")] = "<1.00 poverty ratio"
    out.loc[poverty.between(20, 25, inclusive="both")] = "1.00-1.99 poverty ratio"
    out.loc[poverty.between(30, 38, inclusive="both")] = ">=2.00 poverty ratio"
    return out


def clean_bmi(df: pd.DataFrame) -> pd.Series:
    bmi = numeric(df, "BMICALC")
    return bmi.where(bmi.between(1, 995, inclusive="both"), np.nan)


def make_bmi_category(bmi: pd.Series) -> pd.Series:
    return pd.cut(
        bmi,
        bins=[-np.inf, 18.5, 25, 30, np.inf],
        labels=["underweight", "normal weight", "overweight", "obesity"],
        right=False,
    ).astype("object")


def any_history(df: pd.DataFrame, vars_: list[str]) -> pd.Series:
    pieces = [binary_from_codes(df, var, yes_codes=[2], no_codes=[1]) for var in vars_ if var in df]
    if not pieces:
        return pd.Series(np.nan, index=df.index, dtype="float64")
    frame = pd.concat(pieces, axis=1)
    out = pd.Series(np.nan, index=df.index, dtype="float64")
    out.loc[(frame == 1).any(axis=1)] = 1.0
    out.loc[(frame == 0).all(axis=1)] = 0.0
    return out


def cause_specific_mortality(df: pd.DataFrame, died: pd.Series) -> tuple[pd.Series, pd.Series]:
    code = numeric(df, "MORTUCODLD")
    cvd = pd.Series(np.nan, index=df.index, dtype="float64")
    cancer = pd.Series(np.nan, index=df.index, dtype="float64")
    cvd.loc[died == 0] = 0.0
    cancer.loc[died == 0] = 0.0
    cvd.loc[(died == 1) & code.isin([1, 5])] = 1.0
    cvd.loc[(died == 1) & code.notna() & ~code.isin([1, 5, 96])] = 0.0
    cancer.loc[(died == 1) & (code == 2)] = 1.0
    cancer.loc[(died == 1) & code.notna() & ~code.isin([2, 96])] = 0.0
    return cvd, cancer


def build_followup_months(df: pd.DataFrame, died: pd.Series) -> tuple[pd.Series, str, str]:
    for var in FOLLOWUP_CANDIDATES:
        if var in df:
            return numeric(df, var), var, "Exact follow-up-month variable from extract."

    missing = [var for var in ["YEAR", "QUARTER", "MORTDODY", "MORTDODQ"] if var not in df]
    if missing:
        stop(f"No exact follow-up-month variable was found and quarter-based follow-up cannot be constructed: {missing}")

    year = numeric(df, "YEAR")
    quarter = numeric(df, "QUARTER")
    death_year = numeric(df, "MORTDODY")
    death_quarter = numeric(df, "MORTDODQ")
    start_q = year * 4 + quarter
    censor_q = LMF_CENSOR_YEAR * 4 + LMF_CENSOR_QUARTER
    end_q = pd.Series(censor_q, index=df.index, dtype="float64")
    dead = died == 1
    valid_death_date = death_year.between(1900, LMF_CENSOR_YEAR, inclusive="both") & death_quarter.between(1, 4, inclusive="both")
    end_q.loc[dead & valid_death_date] = death_year.loc[dead & valid_death_date] * 4 + death_quarter.loc[dead & valid_death_date]
    followup = (end_q - start_q) * 3
    followup.loc[dead & valid_death_date & followup.notna() & (followup <= 0)] = 1.5
    followup.loc[dead & ~valid_death_date] = np.nan
    followup.loc[~quarter.between(1, 4, inclusive="both")] = np.nan
    note = (
        "No exact person-month follow-up variable was present in the extract. "
        "Follow-up was approximated in months from survey year/quarter to death "
        "year/quarter or December 31, 2019 for survivors."
    )
    write_issue_once(
        note
        + " The downloaded 2019 LMF variables provide public-use mortality follow-up "
        "through December 31, 2019, not through 2022. Confirm whether an exact "
        "person-month follow-up variable or newer LMF release is required before final models."
    )
    return followup, "YEAR+QUARTER+MORTDODY+MORTDODQ", note


def storable(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if isinstance(out[col].dtype, pd.CategoricalDtype):
            out[col] = out[col].astype("object")
        if out[col].dtype == "object" or str(out[col].dtype) == "string":
            out[col] = out[col].astype("object").where(out[col].notna(), "")
    return out


def write_csv_and_dta(df: pd.DataFrame, stem: str) -> None:
    csv_path = PROCESSED_DIR / f"{stem}.csv"
    dta_path = PROCESSED_DIR / f"{stem}.dta"
    df.to_csv(csv_path, index=False)
    labels = {var: vals for var, vals in VALUE_LABELS_FOR_DTA.items() if var in df.columns}
    pyreadstat.write_dta(storable(df), dta_path, variable_value_labels=labels)


def variable_dictionary(followup_source: str, followup_note: str) -> pd.DataFrame:
    rows = [
        ("person_id", "Unique person identifier", "NHISPID", "String identifier", "Missing if NHISPID unavailable", "IPUMS constructed person ID."),
        ("year", "NHIS survey year", "YEAR", "Calendar year", "Missing if YEAR unavailable", "Alias of survey_year for Stata checks."),
        ("survey_year", "NHIS survey year", "YEAR", "Calendar year", "Missing if YEAR unavailable", ""),
        ("sample_adult", "Sample adult with record", "ASTATFLG", "1 if ASTATFLG==1, else 0", "None", "MSA variables are sample-adult variables."),
        ("adult_18plus", "Age 18 or older", "AGE", "1 if AGE>=18", "Missing if AGE special/missing", ""),
        ("adult_20plus", "Age 20 or older", "AGE", "1 if AGE>=20", "Missing if AGE special/missing", "Sensitivity flag only."),
        ("mortality_linkage_eligible", "Eligible for mortality linkage", "MORTELIG", "1 if MORTELIG==1, else 0", "None", "Public-use linkage is for adults with sufficient linkage data."),
        ("died_allcause", "All-cause mortality indicator", "MORTSTAT", "1 assumed deceased, 0 assumed alive", "Missing if MORTSTAT is NIU/unclassified", ""),
        ("died_cvd", "Cardiovascular mortality indicator", "MORTUCODLD", "1 if death leading cause is heart disease or cerebrovascular disease", "Missing if decedent cause is NIU/unclassified", "Uses public-use leading-cause groups."),
        ("died_cancer", "Cancer mortality indicator", "MORTUCODLD", "1 if death leading cause is malignant neoplasms", "Missing if decedent cause is NIU/unclassified", "Uses public-use leading-cause groups."),
        ("followup_time_months", "Follow-up time for survival analysis", followup_source, "Months", "Missing if follow-up cannot be constructed", followup_note),
        ("followup_time_years", "Follow-up time for survival analysis", "followup_time_months", "Months divided by 12", "Missing if followup_time_months missing", followup_note),
        ("msa_days_week", "MSA weekly frequency", "STRONGFWK", "NCHS recoded times/week; code 94 set to 0.5 and code 95 set to 0", "Codes 00, 93, 96, 97, 98, 99 set missing", "This is times/week used as a days/week proxy; distinct days cannot be verified."),
        ("msa_cat5", "Five-category MSA frequency", "msa_days_week", "0=0 days/week, 1=1, 2=2, 3=3-4, 4=5+", "Missing if msa_days_week missing", "Less than once/week is grouped with 0 days/week."),
        ("msa_guideline", "Meets MSA guideline", "msa_days_week", "1 if >=2 times/week, 0 otherwise", "Missing if msa_days_week missing", ""),
        ("insufficient_msa", "Insufficient MSA", "msa_days_week", "1 if <2 times/week, 0 if >=2", "Missing if msa_days_week missing", ""),
        ("aerobic_minutes_meq_weekly", "Moderate-equivalent aerobic minutes/week", "MOD10FWK MOD10DMIN VIG10FWK VIG10DMIN", "moderate freq*duration + 2*vigorous freq*duration", "Missing if needed aerobic components missing/special", "Uses NCHS recoded weekly frequency and minutes variables."),
        ("aerobic_meets_guideline", "Meets aerobic guideline", "aerobic_minutes_meq_weekly", "1 if >=150 moderate-equivalent minutes/week", "Missing if aerobic minutes missing", ""),
        ("aerobic_category", "Aerobic guideline category", "aerobic_minutes_meq_weekly", "inactive, insufficiently active, meets guideline", "Missing if aerobic minutes missing", ""),
        ("combined_guideline", "Combined MSA/aerobic guideline status", "msa_guideline aerobic_meets_guideline", "neither guideline, MSA only, aerobic only, both guidelines", "Missing if either guideline indicator missing", ""),
        ("age", "Age at interview", "AGE", "Years; 85 is top-coded age 85+", "Missing for special unknown codes", ""),
        ("sex", "Sex", "SEX", "Male/Female labels", "Codes 7/8/9 missing", ""),
        ("race_ethnicity", "Race/ethnicity", "RACEA HISPETH", "Hispanic if HISPETH 20-70; otherwise non-Hispanic race groups", "Unknown race/ethnicity missing", ""),
        ("education", "Educational attainment", "EDUC", "Less than HS, HS/GED, some college/AA, BA, graduate/professional", "Codes 000/996/997/998/999 missing", ""),
        ("poverty", "Poverty-income ratio category", "POVERTY", "<1.00, 1.00-1.99, >=2.00", "Codes 98/99 missing", ""),
        ("marital_status", "Legal marital status", "MARSTAT", "Decoded IPUMS label", "NIU/unknown missing", ""),
        ("region", "US Census region", "REGION", "Decoded IPUMS label", "No data/unknown missing", ""),
        ("bmi", "Body mass index", "BMICALC", "kg/m2; IPUMS CSV already applies the implied decimal", "Codes 0 and 996 missing", ""),
        ("bmi_cat", "BMI category", "bmi", "underweight, normal, overweight, obesity", "Missing if BMI missing", ""),
        ("smoking_status", "Smoking status", "SMOKESTATUS2", "Decoded IPUMS label", "NIU/unknown missing", ""),
        ("alcohol_use", "Alcohol use status", "ALCSTAT1", "Lifetime abstainer, former drinker, current drinker", "NIU/unknown missing", "ALCSTAT1 is available across 1997-2018; ALCSTAT2 is retained as source only."),
        ("self_rated_health", "Self-rated health", "HEALTH", "Excellent, very good, good, fair, poor", "Codes 7/8/9 missing", ""),
        ("diabetes", "Baseline diabetes history", "DIABETICEV", "1 if code 2 yes, 0 if code 1 no", "Borderline/unknown/NIU missing", ""),
        ("hypertension", "Baseline hypertension history", "HYPERTENEV", "1 if code 2 yes, 0 if code 1 no", "Unknown/NIU missing", ""),
        ("cvd_history", "Baseline CVD history", "CHEARTDIEV HEARTATTEV STROKEV", "1 if any source is yes, 0 if all available sources are no", "Missing if source statuses are unresolved", ""),
        ("cancer_history", "Baseline cancer history", "CANCEREV", "1 if code 2 yes, 0 if code 1 no", "Unknown/NIU missing", ""),
        ("weight_mortality", "Primary mortality analysis weight", "MORTWTSA", "MORTWTSA if positive", "Missing/nonpositive set missing", "Correct mortality weight for 1997-2018 sample-adult variables."),
        ("weight_sample_adult", "Sample adult weight", "SAMPWEIGHT", "Positive SAMPWEIGHT", "Missing/nonpositive set missing", "For descriptive checks, not final mortality analysis."),
        ("strata", "Variance stratum", "STRATA", "IPUMS/NHIS design stratum", "000 or missing set missing", ""),
        ("psu", "Primary sampling unit", "PSU", "IPUMS/NHIS design PSU", "000 or missing set missing", ""),
        ("nonmissing_msa", "MSA availability flag", "msa_days_week", "1 if msa_days_week nonmissing", "0 otherwise", ""),
        ("nonmissing_followup", "Follow-up availability flag", "followup_time_months died_allcause", "1 if follow-up and death status nonmissing", "0 otherwise", ""),
        ("complete_case_main", "Main complete-case flag", "Constructed covariates", "1 if no missing main model variables", "0 otherwise", "No final models are estimated here."),
        ("lag24_exclusion", "Early death exclusion flag", "died_allcause followup_time_months", "1 if death within first 24 months", "0 otherwise", ""),
        ("complete_case_lag24", "Lag-24 complete-case flag", "complete_case_main lag24_exclusion", "1 if complete case and not excluded", "0 otherwise", ""),
    ]
    return pd.DataFrame(rows, columns=["variable_name", "description", "source_variables", "coding", "missing_values", "notes"])


def format_years(years: list[int]) -> str:
    if not years:
        return "None"
    if years == list(range(min(years), max(years) + 1)):
        return f"{min(years)}-{max(years)}"
    return ", ".join(str(year) for year in years)


def source_usable_mask(df: pd.DataFrame, var: str) -> pd.Series:
    values = numeric(df, var)
    if var in {"STRONGFWK", "MOD10FWK", "VIG10FWK"}:
        return values.between(1, 92, inclusive="both") | values.isin([94, 95])
    if var in {"STRONGFTP", "MOD10FTP", "VIG10FTP"}:
        return values.isin([1, 2, 3, 4, 5])
    if var in {"STRONGFNO", "MOD10FNO", "VIG10FNO"}:
        period_var = var.replace("FNO", "FTP")
        if period_var in df:
            period = numeric(df, period_var)
            return values.between(1, 994, inclusive="both") | (period == 1)
        return values.between(1, 994, inclusive="both")
    if var in {"MOD10DMIN", "VIG10DMIN"}:
        return values.between(1, 995, inclusive="both") | (values == 0)
    if var == "MORTELIG":
        return values == 1
    if var == "MORTSTAT":
        return values.isin([1, 2])
    if var == "MORTDODQ":
        return values.between(1, 4, inclusive="both")
    if var == "MORTDODY":
        return values.between(1997, LMF_CENSOR_YEAR, inclusive="both")
    if var == "MORTUCODLD":
        return values.between(1, 10, inclusive="both")
    if var == "MORTUCOD":
        return values.between(1, 998, inclusive="both")
    if var in {"MORTWTSA", "SAMPWEIGHT", "PERWEIGHT", "MORTWT"}:
        return values > 0
    if var == "BMICALC":
        return values.between(1, 995, inclusive="both")
    if var == "AGE":
        return values.between(0, 120, inclusive="both")
    if var == "ASTATFLG":
        return values == 1
    if var == "SEX":
        return values.isin([1, 2])
    if var == "RACEA":
        return values.between(100, 699, inclusive="both")
    if var == "HISPETH":
        return values.between(10, 70, inclusive="both")
    if var == "EDUC":
        return values.between(100, 599, inclusive="both")
    if var == "POVERTY":
        return values.between(10, 38, inclusive="both")
    if var == "HEALTH":
        return values.between(1, 5, inclusive="both")
    if var == "SMOKESTATUS2":
        return values.isin([10, 11, 12, 13, 20, 30, 40])
    if var == "ALCSTAT1":
        return values.isin([1, 2, 3])
    if var == "ALCSTAT2":
        return values.isin([10, 20, 21, 22, 23, 30, 31, 32, 33, 34, 35, 40, 41, 42, 43])
    if var in {"DIABETICEV", "HYPERTENEV", "CHEARTDIEV", "HEARTATTEV", "STROKEV", "CANCEREV"}:
        return values.isin([1, 2])
    if var in {"STRATA", "PSU"}:
        return values > 0
    return df[var].notna() if var in df else pd.Series(False, index=df.index)


def coding_summary(var: str, variable_info: dict[str, dict[str, Any]], value_labels: dict[str, dict[Any, str]]) -> str:
    manual = {
        "STRONGFWK": "00 NIU; 1-92 times/week; 93 extreme; 94 less than once/week; 95 never; 96 unable; 97 refused; 98 not ascertained; 99 don't know.",
        "MOD10FWK": "00 NIU; 1-92 times/week; 93 extreme; 94 less than once/week; 95 never; 96 unable; 97 refused; 98 not ascertained; 99 don't know.",
        "VIG10FWK": "00 NIU; 1-92 times/week; 93 extreme; 94 less than once/week; 95 never; 96 unable; 97 refused; 98 not ascertained; 99 don't know.",
        "MOD10DMIN": "000 NIU; 1-995 minutes; 996 extreme; 997 refused; 998 not ascertained; 999 don't know.",
        "VIG10DMIN": "000 NIU; 1-995 minutes; 996 extreme; 997 refused; 998 not ascertained; 999 don't know.",
        "MORTELIG": "1 eligible; 2 under age 18; 3 ineligible; 9 NIU.",
        "MORTSTAT": "1 assumed deceased; 2 assumed alive; 9 NIU.",
        "MORTDODQ": "1 Jan-Mar; 2 Apr-Jun; 3 Jul-Sep; 4 Oct-Dec; 9 NIU.",
        "MORTDODY": "Death year 1997-2019 in this extract; 9999 NIU.",
        "MORTUCODLD": "01 heart; 02 malignant neoplasms; 03 CLRD; 04 accidents; 05 cerebrovascular; 06 Alzheimer's; 07 diabetes; 08 influenza/pneumonia; 09 nephritis; 10 residual; 96 NIU.",
        "MORTWTSA": "Positive sample-adult mortality weight; 0 outside the eligible sample-adult mortality universe.",
        "SAMPWEIGHT": "Positive sample adult/person supplement weight; 0 outside universe.",
        "BMICALC": "BMI kg/m2 in IPUMS CSV; 0 NIU; 996 not calculable.",
    }
    if var in manual:
        return manual[var]
    labels = value_labels.get(var, {})
    if labels:
        string_keys = [(str(k), v) for k, v in labels.items() if isinstance(k, str)]
        if not string_keys:
            string_keys = [(str(k), v) for k, v in labels.items()]
        return "; ".join(f"{k} {v}" for k, v in string_keys[:10])
    instr = variable_info.get(var, {}).get("cod_instr", "")
    return instr[:220] if instr else "Continuous/string variable; see DDI XML."


def create_variable_availability_report(
    df: pd.DataFrame,
    variable_info: dict[str, dict[str, Any]],
    value_labels: dict[str, dict[Any, str]],
    followup_source: str,
    followup_note: str,
) -> None:
    concepts = [
        ("Survey year", "YEAR", "Yes", ""),
        ("Person identifier", "NHISPID", "Yes", ""),
        ("Sample/adult status", "ASTATFLG", "Yes", "Main analysis requires ASTATFLG==1."),
        ("Age", "AGE", "Yes", "Age 85 is top-coded as 85+."),
        ("Sex", "SEX", "Yes", ""),
        ("Race", "RACEA", "Yes", "Combined with HISPETH into race_ethnicity."),
        ("Hispanic ethnicity", "HISPETH", "Yes", "Combined with RACEA into race_ethnicity."),
        ("Education", "EDUC", "Yes", "Collapsed into five education categories."),
        ("Poverty-income ratio", "POVERTY", "Yes", "Categorical poverty ratio, not continuous income."),
        ("BMI", "BMICALC", "Yes", ""),
        ("Smoking", "SMOKESTATUS2", "Yes", ""),
        ("Alcohol use", "ALCSTAT1", "Yes", "ALCSTAT1 is used because it is available in all extract years."),
        ("Detailed alcohol status", "ALCSTAT2", "No", "Only available 2001-2013 in this extract; retained as source only."),
        ("Self-rated health", "HEALTH", "Yes", ""),
        ("Diabetes", "DIABETICEV", "Yes", "Borderline diabetes is set missing, not yes."),
        ("Hypertension", "HYPERTENEV", "Yes", ""),
        ("Coronary heart disease", "CHEARTDIEV", "Yes", "Used with HEARTATTEV/STROKEV for CVD history."),
        ("Heart attack", "HEARTATTEV", "Yes", "Used with CHEARTDIEV/STROKEV for CVD history."),
        ("Stroke", "STROKEV", "Yes", "Used with CHEARTDIEV/HEARTATTEV for CVD history."),
        ("Cancer history", "CANCEREV", "Yes", ""),
        ("Moderate aerobic frequency", "MOD10FWK", "Yes", ""),
        ("Moderate aerobic duration", "MOD10DMIN", "Yes", ""),
        ("Vigorous aerobic frequency", "VIG10FWK", "Yes", ""),
        ("Vigorous aerobic duration", "VIG10DMIN", "Yes", ""),
        ("MSA original number", "STRONGFNO", "Source only", "Used to verify STRONGFWK but not directly in analysis."),
        ("MSA original time period", "STRONGFTP", "Source only", "Shows original periods: never/day/week/month/year/special."),
        ("MSA weekly frequency", "STRONGFWK", "Yes", "Main MSA source; times/week, not literal distinct days/week."),
        ("Mortality eligibility", "MORTELIG", "Yes", ""),
        ("Vital status/all-cause mortality", "MORTSTAT", "Yes", ""),
        ("Death quarter", "MORTDODQ", "Yes", "Used only for deceased respondents in approximate follow-up."),
        ("Death year", "MORTDODY", "Yes", "Maximum observed death year is 2019."),
        ("Detailed cause of death", "MORTUCOD", "Limited", "Only available for 1997-2004 samples in this extract."),
        ("Leading cause of death", "MORTUCODLD", "Yes", "Public-use 10-category leading cause variable."),
        ("Person-file mortality weight", "MORTWT", "No", "Not used for sample-adult MSA analysis; unavailable after 2014."),
        ("Sample-adult mortality weight", "MORTWTSA", "Yes", "Primary mortality analysis weight."),
        ("Survey/sample adult weight", "SAMPWEIGHT", "Descriptive", "Not used for mortality stset; retained for checks."),
        ("Strata", "STRATA", "Yes", ""),
        ("PSU", "PSU", "Yes", ""),
    ]
    raw_n = len(df)
    year = numeric(df, "YEAR")
    rows = []
    for concept, var, usable, concern in concepts:
        if var not in df:
            rows.append([concept, var, "Missing from extract", "", "None", f"{raw_n} (100.0%)", "No", "Missing from CSV."])
            continue
        present = df[var].notna()
        if df[var].dtype == object or str(df[var].dtype) == "string":
            present = present & (df[var].astype("string").str.strip() != "")
        available_years = sorted(int(y) for y in year.loc[present & year.notna()].dropna().unique())
        usable_mask = source_usable_mask(df, var)
        usable_years = sorted(int(y) for y in year.loc[usable_mask & year.notna()].dropna().unique())
        missing_special = raw_n - int(usable_mask.sum())
        label = variable_info.get(var, {}).get("label", "")
        rows.append(
            [
                concept,
                var,
                label,
                coding_summary(var, variable_info, value_labels),
                format_years(available_years),
                f"{missing_special:,} ({missing_special / raw_n:.1%}) missing/special or outside usable coding",
                usable,
                concern,
            ]
        )

    report_lines = [
        "# Variable Availability Report",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "Inputs inspected: `nhis_00001.xml`, `nhis_00001.cbk`, `nhis_00001.sts`, and the header of `nhis_00001.csv.gz`.",
        "",
        f"Raw observations: {raw_n:,}. Survey years in CSV: {format_years(sorted(int(y) for y in year.dropna().unique()))}.",
        "",
        "## Source Variable Map",
        "",
        "| Concept | Exact IPUMS variable | Variable label | Coding summary | Years available | Missingness | Usable for main analysis | Concerns |",
        "|---|---|---|---|---|---:|---|---|",
    ]
    for row in rows:
        safe = [str(cell).replace("|", "\\|") for cell in row]
        report_lines.append("| " + " | ".join(safe) + " |")

    strong = numeric(df, "STRONGFWK")
    strong_valid = source_usable_mask(df, "STRONGFWK")
    valid_years = sorted(int(y) for y in year.loc[strong_valid & year.notna()].unique())
    strong_counts = strong.value_counts(dropna=False).sort_index()
    special_counts = {code: int((strong == code).sum()) for code in [0, 93, 94, 95, 96, 97, 98, 99]}
    report_lines.extend(
        [
            "",
            "## MSA Verification",
            "",
            "- `STRONGFWK` is the main MSA source. IPUMS labels it `Frequency of strengthening activity: Times per week`.",
            "- It is an NCHS recode from `STRONGFNO` plus `STRONGFTP`; it is not a literal distinct-days-per-week measure.",
            "- Main conversion: codes 1-92 retain their weekly frequency, code 94 is coded as 0.5 for less than once/week, and code 95 is coded as 0.",
            "- Codes 00 NIU, 93 extreme, 96 unable, 97 refused, 98 not ascertained, and 99 don't know are set missing for `msa_days_week`.",
            f"- Valid MSA data are present in {format_years(valid_years)}.",
            f"- Key `STRONGFWK` counts in the raw extract: {json.dumps(special_counts)}.",
            "- `msa_cat5` groups less-than-weekly values with 0 days/week for the requested five-category exposure.",
            "",
            "## Mortality Linkage Verification",
            "",
            "- `MORTELIG==1` identifies respondents eligible for public-use mortality linkage.",
            "- `MORTSTAT==1` is assumed deceased and `MORTSTAT==2` is assumed alive.",
            "- `MORTWTSA` is used as the mortality weight because the exposure and covariates are sample-adult variables for 1997-2018.",
            "- No exact person-month follow-up variable was present in this extract.",
            f"- Follow-up source used here: `{followup_source}`. {followup_note}",
            "- The DDI text for the included mortality variables states that the 2019 LMF update follows mortality through December 31, 2019. This extract does not provide follow-up through 2022.",
            "- Cause-specific mortality is limited to public-use leading-cause groups in `MORTUCODLD`; detailed `MORTUCOD` is unavailable for 2005-2018 samples.",
        ]
    )
    (LOG_DIR / "variable_availability_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")


def main() -> None:
    ensure_dirs()
    data_path = find_data_file()
    df, variable_info, variable_labels, value_labels = read_data_and_metadata(data_path)
    metadata_vars = set(variable_labels) | set(value_labels) | set(df.columns)
    missing_required = [var for var in REQUIRED_SOURCES if var not in df.columns or var not in metadata_vars]
    if missing_required:
        stop(f"Required source variables are missing from data/metadata: {missing_required}")

    out = pd.DataFrame(index=df.index)
    age = numeric(df, "AGE")
    out["person_id"] = df["NHISPID"].astype("string").str.strip()
    out["year"] = numeric(df, "YEAR")
    out["survey_year"] = out["year"]
    out["sample_adult"] = (numeric(df, "ASTATFLG") == 1).astype(int)
    out["adult_18plus"] = np.where(age.notna(), (age >= 18).astype(int), np.nan)
    out["adult_20plus"] = np.where(age.notna(), (age >= 20).astype(int), np.nan)
    out["mortality_linkage_eligible"] = (numeric(df, "MORTELIG") == 1).astype(int)
    out["died_allcause"] = np.where(
        numeric(df, "MORTSTAT") == 1,
        1,
        np.where(numeric(df, "MORTSTAT") == 2, 0, np.nan),
    )
    out["followup_time_months"], followup_source, followup_note = build_followup_months(df, out["died_allcause"])
    out["followup_time_years"] = out["followup_time_months"] / 12
    out["nonmissing_followup"] = (
        out["followup_time_months"].notna()
        & (out["followup_time_months"] > 0)
        & out["died_allcause"].notna()
    ).astype(int)

    out["msa_days_week"] = recode_weekly_frequency(df, "STRONGFWK")
    out["nonmissing_msa"] = out["msa_days_week"].notna().astype(int)
    out["msa_cat5"] = make_msa_category(out["msa_days_week"])
    out["msa_cat5_label"] = msa_category_label(out["msa_cat5"])
    out["msa_guideline"] = np.where(out["msa_days_week"].notna(), (out["msa_days_week"] >= 2).astype(int), np.nan)
    out["insufficient_msa"] = np.where(out["msa_days_week"].notna(), (out["msa_days_week"] < 2).astype(int), np.nan)

    mod_freq = recode_weekly_frequency(df, "MOD10FWK")
    vig_freq = recode_weekly_frequency(df, "VIG10FWK")
    mod_dur = recode_duration_minutes(df, "MOD10DMIN", mod_freq)
    vig_dur = recode_duration_minutes(df, "VIG10DMIN", vig_freq)
    out["moderate_minutes_weekly"] = mod_freq * mod_dur
    out["vigorous_minutes_weekly"] = vig_freq * vig_dur
    out["aerobic_minutes_meq_weekly"] = out["moderate_minutes_weekly"] + 2 * out["vigorous_minutes_weekly"]
    out["aerobic_meets_guideline"] = np.where(
        out["aerobic_minutes_meq_weekly"].notna(),
        (out["aerobic_minutes_meq_weekly"] >= 150).astype(int),
        np.nan,
    )
    out["aerobic_category"] = make_aerobic_category(out["aerobic_minutes_meq_weekly"])
    out["aerobic_guideline_cat"] = out["aerobic_category"]
    out["combined_guideline"] = pd.NA
    out.loc[(out["msa_guideline"] == 0) & (out["aerobic_meets_guideline"] == 0), "combined_guideline"] = "neither guideline"
    out.loc[(out["msa_guideline"] == 1) & (out["aerobic_meets_guideline"] == 0), "combined_guideline"] = "MSA only"
    out.loc[(out["msa_guideline"] == 0) & (out["aerobic_meets_guideline"] == 1), "combined_guideline"] = "aerobic only"
    out.loc[(out["msa_guideline"] == 1) & (out["aerobic_meets_guideline"] == 1), "combined_guideline"] = "both guidelines"

    out["age"] = age.where(age.between(0, 120, inclusive="both"), np.nan)
    out["age_cat"] = pd.cut(
        out["age"],
        bins=[18, 35, 45, 55, 65, 75, np.inf],
        labels=["18-34", "35-44", "45-54", "55-64", "65-74", "75+"],
        right=False,
    ).astype("object")
    out["sex"] = clean_decoded(df, "SEX", value_labels)
    out["race_ethnicity"] = race_ethnicity(df)
    out["education"] = education_category(df)
    out["poverty"] = poverty_category(df)
    out["marital_status"] = clean_decoded(df, "MARSTAT", value_labels)
    out["region"] = clean_decoded(df, "REGION", value_labels)

    out["bmi"] = clean_bmi(df)
    out["bmi_cat"] = make_bmi_category(out["bmi"])
    out["smoking_status"] = clean_decoded(df, "SMOKESTATUS2", value_labels)
    out["alcohol_use"] = clean_decoded(df, "ALCSTAT1", value_labels)
    out["self_rated_health"] = clean_decoded(df, "HEALTH", value_labels)
    out["diabetes"] = binary_from_codes(df, "DIABETICEV", yes_codes=[2], no_codes=[1])
    out["hypertension"] = binary_from_codes(df, "HYPERTENEV", yes_codes=[2], no_codes=[1])
    out["cvd_history"] = any_history(df, ["CHEARTDIEV", "HEARTATTEV", "STROKEV"])
    out["cancer_history"] = binary_from_codes(df, "CANCEREV", yes_codes=[2], no_codes=[1])
    out["died_cvd"], out["died_cancer"] = cause_specific_mortality(df, out["died_allcause"])

    out["weight_mortality"] = numeric(df, "MORTWTSA").where(numeric(df, "MORTWTSA") > 0, np.nan)
    out["weight_sample_adult"] = numeric(df, "SAMPWEIGHT").where(numeric(df, "SAMPWEIGHT") > 0, np.nan)
    out["strata"] = numeric(df, "STRATA").where(numeric(df, "STRATA") > 0, np.nan)
    out["psu"] = numeric(df, "PSU").where(numeric(df, "PSU") > 0, np.nan)

    for covar in [
        "msa_days_week",
        "followup_time_months",
        "aerobic_minutes_meq_weekly",
        "age",
        "sex",
        "race_ethnicity",
        "education",
        "poverty",
        "marital_status",
        "region",
        "bmi",
        "smoking_status",
        "alcohol_use",
        "self_rated_health",
        "diabetes",
        "hypertension",
        "cvd_history",
        "cancer_history",
        "weight_mortality",
    ]:
        out[f"miss_{covar}"] = out[covar].isna().astype(int)

    out["lag24_exclusion"] = ((out["died_allcause"] == 1) & (out["followup_time_months"] <= 24)).astype(int)
    available_complete_vars = [var for var in COMPLETE_CASE_VARS if var in out.columns]
    out["complete_case_main"] = out[available_complete_vars].notna().all(axis=1).astype(int)
    out.loc[
        ~(
            (out["adult_18plus"] == 1)
            & (out["sample_adult"] == 1)
            & (out["mortality_linkage_eligible"] == 1)
            & (out["nonmissing_followup"] == 1)
            & (out["nonmissing_msa"] == 1)
        ),
        "complete_case_main",
    ] = 0
    out["complete_case_lag24"] = ((out["complete_case_main"] == 1) & (out["lag24_exclusion"] == 0)).astype(int)

    source_cols = {f"src_{var.lower()}": df[var] for var in SOURCE_KEEPERS if var in df}
    if source_cols:
        out = pd.concat([out, pd.DataFrame(source_cols, index=df.index)], axis=1)

    raw_n = len(out)
    adults = out["adult_18plus"] == 1
    adult_sample = adults & (out["sample_adult"] == 1)
    eligible = adult_sample & (out["mortality_linkage_eligible"] == 1)
    nonmissing_followup = eligible & (out["nonmissing_followup"] == 1)
    nonmissing_msa = nonmissing_followup & (out["nonmissing_msa"] == 1)
    full = out.loc[nonmissing_followup].copy()
    complete = full.loc[full["complete_case_main"] == 1].copy()
    lag24 = full.loc[full["complete_case_lag24"] == 1].copy()

    if full.empty:
        stop("After adult sample-adult, mortality linkage, and follow-up restrictions, no observations remain.")
    if complete.empty:
        stop("The main complete-case dataset is empty. Review missingness before continuing.")

    flow = [
        ("raw observations", raw_n),
        ("adults 18+", int(adults.sum())),
        ("sample adults 18+", int(adult_sample.sum())),
        ("eligible for mortality linkage", int(eligible.sum())),
        ("non-missing follow-up", int(nonmissing_followup.sum())),
        ("non-missing MSA", int(nonmissing_msa.sum())),
        ("complete case", int(len(complete))),
        ("complete case excluding first 24 months", int(len(lag24))),
    ]
    build_meta = {
        "run_time": datetime.now().isoformat(timespec="seconds"),
        "raw_data_file": str(data_path.relative_to(PROJECT_ROOT)),
        "followup_source": followup_source,
        "followup_note": followup_note,
        "sample_flow": [{"stage": stage, "n": n} for stage, n in flow],
        "survey_years_in_full": sorted(int(year) for year in full["year"].dropna().unique()),
        "msa_variable_used": "STRONGFWK",
        "mortality_weight_used": "MORTWTSA",
    }
    (INTERIM_DIR / "msa_build_metadata.json").write_text(json.dumps(build_meta, indent=2) + "\n", encoding="utf-8")

    create_variable_availability_report(df, variable_info, value_labels, followup_source, followup_note)
    write_csv_and_dta(full, "msa_survival_full")
    write_csv_and_dta(complete, "msa_survival_main_completecase")
    write_csv_and_dta(lag24, "msa_survival_lag24_completecase")
    variable_dictionary(followup_source, followup_note).to_csv(PROCESSED_DIR / "msa_variable_dictionary.csv", index=False)

    print("Processed datasets created in data/processed/.")
    print(pd.DataFrame(flow, columns=["stage", "n"]).to_string(index=False))
    print(f"Follow-up source: {followup_source}")
    print("MSA source: STRONGFWK")


if __name__ == "__main__":
    main()
