"""First burden pipeline for insufficient MSA.

This script estimates weighted prevalence of insufficient muscle-strengthening
activity (MSA), applies the refined Cox HR as a comparative-risk input, and
computes preliminary PAFs. It only computes attributable deaths and YLL if
external official inputs are present. It never fabricates external mortality,
life table, or economic data.
"""

from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "data/processed"
EXTERNAL_DIR = PROJECT_ROOT / "data/external"
DOCS_DIR = PROJECT_ROOT / "docs"
LOG_DIR = PROJECT_ROOT / "outputs/logs"
TABLE_DIR = PROJECT_ROOT / "outputs/tables"

FULL_DATA = PROCESSED_DIR / "msa_survival_full.csv"
NHIS2024_DATA = PROCESSED_DIR / "nhis_2024/nhis_2024_msa_prevalence_dataset.csv"
REFINED_COX = TABLE_DIR / "refined_cox_msa_allcause.csv"
REVIEWER_COX = TABLE_DIR / "reviewer_cox_sensitivity.csv"
DECISION_REPORT = TABLE_DIR / "refined_cox_decision_report.md"
ISSUES = LOG_DIR / "issues_to_resolve.md"
RUN_LOG = LOG_DIR / "06_burden_paf_deaths_yll.log"

PREVALENCE_OUT = TABLE_DIR / "msa_prevalence_insufficient.csv"
PAF_OUT = TABLE_DIR / "msa_paf_insufficient.csv"
PAF_MC_OUT = TABLE_DIR / "msa_paf_insufficient_montecarlo.csv"
PREVALENCE_PERIOD_OUT = TABLE_DIR / "msa_prevalence_insufficient_by_period.csv"
PAF_PERIOD_OUT = TABLE_DIR / "msa_paf_insufficient_by_period.csv"
PAF_MC_PERIOD_OUT = TABLE_DIR / "msa_paf_insufficient_montecarlo_by_period.csv"
PAF_NHIS2024_OUT = TABLE_DIR / "msa_paf_insufficient_using_nhis2024.csv"
PAF_MC_NHIS2024_OUT = TABLE_DIR / "msa_paf_insufficient_montecarlo_using_nhis2024.csv"
HR_INPUTS_OUT = TABLE_DIR / "hr_inputs_for_burden.csv"
NHIS2024_PREMATURE_OVERALL = TABLE_DIR / "nhis_2024_msa_prevalence_premature_30_69_overall.csv"
NHIS2024_PREMATURE_SEX = TABLE_DIR / "nhis_2024_msa_prevalence_premature_30_69_by_sex.csv"
NHIS2024_PREMATURE_AGE = TABLE_DIR / "nhis_2024_msa_prevalence_premature_30_69_by_age.csv"
NHIS2024_PREMATURE_AGE_SEX = TABLE_DIR / "nhis_2024_msa_prevalence_premature_30_69_by_age_sex.csv"
PAF_PREMATURE_OUT = TABLE_DIR / "msa_paf_insufficient_premature_30_69_nhis2024.csv"
PAF_MC_PREMATURE_OUT = TABLE_DIR / "msa_paf_insufficient_montecarlo_premature_30_69_nhis2024.csv"
DEATHS_OUT = TABLE_DIR / "msa_attributable_deaths.csv"
YLL_OUT = TABLE_DIR / "msa_yll.csv"
PRODUCTIVITY_OUT = TABLE_DIR / "msa_productivity_losses.csv"
READINESS_OUT = TABLE_DIR / "burden_readiness_report.md"

N_DRAWS = 10_000
RNG_SEED = 20260429
MAIN_PRESENT_DAY_PERIOD = "recent_pooled_2015_2018"
NHIS2024_PERIOD = "nhis_2024_current"
PREMATURE_PERIOD = "premature_30_69"


def ensure_dirs() -> None:
    for path in [EXTERNAL_DIR, DOCS_DIR, LOG_DIR, TABLE_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def write_csv_preserve_existing(df: pd.DataFrame, path: Path, *, preserve_existing: bool = False) -> bool:
    """Write a CSV unless an existing legacy output should be retained."""
    if preserve_existing and path.exists():
        return False
    df.to_csv(path, index=False)
    return True


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


def write_template(path: Path, columns: list[str]) -> None:
    if not path.exists():
        pd.DataFrame(columns=columns).to_csv(path, index=False)


def write_doc(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def create_external_templates() -> None:
    write_template(
        EXTERNAL_DIR / "us_allcause_deaths_template.csv",
        ["year", "sex", "age_group", "deaths_allcause", "source", "notes"],
    )
    write_doc(
        DOCS_DIR / "external_mortality_data_needed.md",
        """# External mortality data needed

Official US all-cause death counts are required before attributable deaths can
be estimated. The preferred source is NCHS/CDC WONDER or another official NCHS
mortality file.

Required columns:

- `year`
- `sex`
- `age_group`
- `deaths_allcause`
- `source`
- `notes`

The `sex` and `age_group` values should match the processed NHIS burden strata
used in `outputs/tables/msa_prevalence_insufficient.csv`. Do not enter
estimated or placeholder death counts.
""",
    )

    write_template(
        EXTERNAL_DIR / "us_life_table_template.csv",
        ["year", "sex", "age_group", "remaining_life_expectancy", "source", "notes"],
    )
    write_doc(
        DOCS_DIR / "external_life_table_data_needed.md",
        """# External life table data needed

Official remaining life expectancy by age group and sex is required before YLL
can be estimated. Use an official US life table source and document the exact
year, table, and age-group mapping.

Required columns:

- `year`
- `sex`
- `age_group`
- `remaining_life_expectancy`
- `source`
- `notes`

The `sex` and `age_group` values should match the mortality input and processed
NHIS burden strata. Do not enter estimated or placeholder life expectancy
values.
""",
    )

    write_template(
        EXTERNAL_DIR / "us_productivity_inputs_template.csv",
        [
            "year",
            "sex",
            "age_group",
            "employment_rate",
            "annual_earnings",
            "productive_years_remaining",
            "gdp_per_employed_person",
            "source",
            "notes",
        ],
    )
    write_doc(
        DOCS_DIR / "external_productivity_data_needed.md",
        """# External productivity inputs needed

Productivity losses are scaffolded but are not final in the current pipeline.
Before computing productivity costs, provide documented official or otherwise
defensible inputs for employment, earnings, productive years remaining, and/or
GDP per employed person.

Required columns:

- `year`
- `sex`
- `age_group`
- `employment_rate`
- `annual_earnings`
- `productive_years_remaining`
- `gdp_per_employed_person`
- `source`
- `notes`

The cost framework should be documented before final productivity losses are
reported.
""",
    )


def required_columns(path: Path, columns: list[str]) -> None:
    if not path.exists():
        stop("Missing required input", f"Required input not found: `{path}`.")
    header = pd.read_csv(path, nrows=0).columns.tolist()
    missing = [col for col in columns if col not in header]
    if missing:
        stop("Missing required columns", f"`{path}` is missing required columns: {', '.join(missing)}.")


def weighted_summary(df: pd.DataFrame, stratum: str, year: str, age_group: str, sex: str) -> dict[str, object]:
    weights = pd.to_numeric(df["weight_sample_adult"], errors="coerce")
    exposure = pd.to_numeric(df["insufficient_msa"], errors="coerce")
    valid = exposure.notna() & weights.notna() & (weights > 0)
    sub = df.loc[valid]
    weights = weights.loc[valid]
    exposure = exposure.loc[valid]
    weighted_total = float(weights.sum())
    weighted_exposed = float((weights * exposure).sum())
    prevalence = weighted_exposed / weighted_total if weighted_total > 0 else np.nan
    return {
        "stratum": stratum,
        "year": year,
        "age_group": age_group,
        "sex": sex,
        "n_unweighted": int(len(sub)),
        "n_exposed": int(exposure.sum()),
        "weighted_total": weighted_total,
        "weighted_exposed": weighted_exposed,
        "prevalence_insufficient_msa": prevalence,
    }


def build_prevalence(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    rows.append(weighted_summary(df, "overall", "all", "all", "all"))

    for age_group, sub in df.dropna(subset=["age_group"]).groupby("age_group", dropna=True, sort=True):
        rows.append(weighted_summary(sub, "age_group", "all", str(age_group), "all"))

    for sex, sub in df.dropna(subset=["sex"]).groupby("sex", dropna=True, sort=True):
        rows.append(weighted_summary(sub, "sex", "all", "all", str(sex)))

    for (age_group, sex), sub in df.dropna(subset=["age_group", "sex"]).groupby(["age_group", "sex"], dropna=True, sort=True):
        rows.append(weighted_summary(sub, "age_group_sex", "all", str(age_group), str(sex)))

    for year, sub in df.groupby("year", dropna=False, sort=True):
        year_value = str(int(year)) if pd.notna(year) and float(year).is_integer() else str(year)
        rows.append(weighted_summary(sub, "survey_year", year_value, "all", "all"))

    out = pd.DataFrame(rows)
    return out.sort_values(["stratum", "year", "age_group", "sex"]).reset_index(drop=True)


def define_target_periods(df: pd.DataFrame) -> list[dict[str, object]]:
    years = sorted(int(year) for year in df["year"].dropna().unique())
    if not years:
        stop("No survey years for burden periods", "No valid survey years were available for period-specific prevalence estimation.")
    available_years = set(years)
    latest_year = max(years)
    periods = [
        {
            "target_period": "full_pooled_1997_2018",
            "target_period_label": "Full pooled period 1997-2018",
            "period_role": "historical pooled sensitivity",
            "start_year": 1997,
            "end_year": 2018,
            "main_present_day_prevalence": 0,
        },
        {
            "target_period": MAIN_PRESENT_DAY_PERIOD,
            "target_period_label": "Recent pooled period 2015-2018",
            "period_role": "preferred present-day prevalence",
            "start_year": 2015,
            "end_year": 2018,
            "main_present_day_prevalence": 1,
        },
        {
            "target_period": f"latest_year_{latest_year}",
            "target_period_label": f"Latest available survey year {latest_year}",
            "period_role": "single-year recency sensitivity",
            "start_year": latest_year,
            "end_year": latest_year,
            "main_present_day_prevalence": 0,
        },
    ]

    for period in periods:
        requested = list(range(int(period["start_year"]), int(period["end_year"]) + 1))
        included = [year for year in requested if year in available_years]
        if not included:
            stop(
                "Target burden period unavailable",
                f"No survey years were available for target period `{period['target_period']}`.",
            )
        missing = [year for year in requested if year not in available_years]
        if missing:
            append_issue_once(
                f"Target period {period['target_period']} has missing years",
                f"The target period `{period['target_period']}` requested years {requested}, but the processed prevalence file only includes {included}. Missing years: {missing}.",
            )
        period["years_included"] = ";".join(str(year) for year in included)
    return periods


def add_period_metadata(summary: dict[str, object], period: dict[str, object]) -> dict[str, object]:
    return {
        "target_period": period["target_period"],
        "target_period_label": period["target_period_label"],
        "period_role": period["period_role"],
        "main_present_day_prevalence": period["main_present_day_prevalence"],
        "period_start_year": period["start_year"],
        "period_end_year": period["end_year"],
        "years_included": period["years_included"],
        **summary,
    }


def build_prevalence_by_period(df: pd.DataFrame, periods: list[dict[str, object]]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for period in periods:
        years = [int(year) for year in str(period["years_included"]).split(";")]
        period_df = df.loc[df["year"].isin(years)].copy()
        rows.append(add_period_metadata(weighted_summary(period_df, "overall", "all", "all", "all"), period))

        for sex, sub in period_df.dropna(subset=["sex"]).groupby("sex", dropna=True, sort=True):
            rows.append(add_period_metadata(weighted_summary(sub, "sex", "all", "all", str(sex)), period))

        for age_group, sub in period_df.dropna(subset=["age_group"]).groupby("age_group", dropna=True, sort=True):
            rows.append(add_period_metadata(weighted_summary(sub, "age_group", "all", str(age_group), "all"), period))

        for (age_group, sex), sub in period_df.dropna(subset=["age_group", "sex"]).groupby(["age_group", "sex"], dropna=True, sort=True):
            rows.append(add_period_metadata(weighted_summary(sub, "age_group_sex", "all", str(age_group), str(sex)), period))

    out = pd.DataFrame(rows)
    order = [
        "target_period",
        "target_period_label",
        "period_role",
        "main_present_day_prevalence",
        "period_start_year",
        "period_end_year",
        "years_included",
        "stratum",
        "year",
        "age_group",
        "sex",
        "n_unweighted",
        "n_exposed",
        "weighted_total",
        "weighted_exposed",
        "prevalence_insufficient_msa",
    ]
    return out[order].sort_values(["target_period", "stratum", "age_group", "sex"]).reset_index(drop=True)


def read_nhis2024_prevalence_frame() -> tuple[pd.DataFrame | None, dict[str, float] | None]:
    if not NHIS2024_DATA.exists():
        append_issue_once(
            "NHIS 2024 prevalence dataset missing",
            "`data/processed/nhis_2024/nhis_2024_msa_prevalence_dataset.csv` was not found. "
            "The burden script retained recent pooled 2015-2018 as the preferred present-day prevalence until NHIS 2024 is built.",
        )
        return None, None

    required = [
        "survey_year",
        "sample_adult",
        "adult_18plus",
        "weight_sample_adult",
        "age_group",
        "sex",
        "msa_guideline_2024",
        "insufficient_msa_2024",
    ]
    header = pd.read_csv(NHIS2024_DATA, nrows=0).columns.tolist()
    missing = [col for col in required if col not in header]
    if missing:
        append_issue_once(
            "NHIS 2024 prevalence dataset missing required columns",
            f"`{NHIS2024_DATA}` is missing columns needed for burden PAF linkage: {', '.join(missing)}. "
            "The burden script retained recent pooled 2015-2018 as the preferred present-day prevalence.",
        )
        return None, None

    df = pd.read_csv(NHIS2024_DATA, usecols=required + [col for col in ["source"] if col in header], low_memory=False)
    sample_adult = pd.to_numeric(df["sample_adult"], errors="coerce")
    adult_18plus = pd.to_numeric(df["adult_18plus"], errors="coerce")
    weights = pd.to_numeric(df["weight_sample_adult"], errors="coerce")
    insufficient = pd.to_numeric(df["insufficient_msa_2024"], errors="coerce")
    meets = pd.to_numeric(df["msa_guideline_2024"], errors="coerce")
    valid = (sample_adult == 1) & (adult_18plus == 1) & weights.notna() & (weights > 0) & insufficient.notna()
    if not valid.any():
        append_issue_once(
            "NHIS 2024 prevalence dataset has no valid analytic rows",
            "`data/processed/nhis_2024/nhis_2024_msa_prevalence_dataset.csv` was present but had no adult sample rows with positive weights and nonmissing MSA.",
        )
        return None, None

    work = pd.DataFrame(
        {
            "year": pd.to_numeric(df.loc[valid, "survey_year"], errors="coerce"),
            "sample_adult": sample_adult.loc[valid],
            "adult_18plus": adult_18plus.loc[valid],
            "insufficient_msa": insufficient.loc[valid],
            "weight_sample_adult": weights.loc[valid],
            "age_group": df.loc[valid, "age_group"],
            "sex": df.loc[valid, "sex"],
        }
    )
    weight_valid = weights.loc[valid]
    summary = {
        "n_unweighted": int(valid.sum()),
        "weighted_total": float(weight_valid.sum()),
        "prevalence_meets_msa_guideline": float((weight_valid * meets.loc[valid]).sum() / weight_valid.sum()),
        "prevalence_insufficient_msa": float((weight_valid * insufficient.loc[valid]).sum() / weight_valid.sum()),
        "source": str(df["source"].dropna().iloc[0]) if "source" in df and df["source"].notna().any() else "unknown",
    }
    return work, summary


def build_nhis2024_period_prevalence() -> tuple[pd.DataFrame | None, dict[str, float] | None]:
    df, summary = read_nhis2024_prevalence_frame()
    if df is None:
        return None, None
    period = {
        "target_period": NHIS2024_PERIOD,
        "target_period_label": "NHIS 2024 current prevalence",
        "period_role": "preferred current prevalence",
        "start_year": 2024,
        "end_year": 2024,
        "main_present_day_prevalence": 1,
        "years_included": "2024",
    }
    return build_prevalence_by_period(df, [period]), summary


def read_prevalence_frame() -> tuple[pd.DataFrame, dict[str, int]]:
    required = [
        "year",
        "sample_adult",
        "adult_18plus",
        "insufficient_msa",
        "weight_sample_adult",
        "sex",
    ]
    header = pd.read_csv(FULL_DATA, nrows=0).columns.tolist()
    age_col = "age_cat" if "age_cat" in header else "age"
    usecols = required + [age_col]
    required_columns(FULL_DATA, usecols)

    df = pd.read_csv(FULL_DATA, usecols=usecols, low_memory=False)
    df = df.rename(columns={age_col: "age_group"})

    sample_adult = pd.to_numeric(df["sample_adult"], errors="coerce")
    adult_18plus = pd.to_numeric(df["adult_18plus"], errors="coerce")
    insufficient = pd.to_numeric(df["insufficient_msa"], errors="coerce")
    weights = pd.to_numeric(df["weight_sample_adult"], errors="coerce")

    counts = {
        "rows_read": int(len(df)),
        "sample_adult_18plus": int(((sample_adult == 1) & (adult_18plus == 1)).sum()),
        "eligible_for_prevalence": int(((sample_adult == 1) & (adult_18plus == 1) & insufficient.notna() & weights.notna() & (weights > 0)).sum()),
    }

    prevalence_df = df.loc[(sample_adult == 1) & (adult_18plus == 1) & insufficient.notna() & weights.notna() & (weights > 0)].copy()
    prevalence_df["insufficient_msa"] = insufficient.loc[prevalence_df.index].astype(float)
    prevalence_df["weight_sample_adult"] = weights.loc[prevalence_df.index].astype(float)
    prevalence_df["year"] = pd.to_numeric(prevalence_df["year"], errors="coerce")

    if prevalence_df.empty:
        stop("No prevalence analytic rows", "No adult sample rows had non-missing insufficient_msa and positive weight_sample_adult.")
    return prevalence_df, counts


def choose_hr(rows: pd.DataFrame, candidates: list[tuple[str, str, str, str, str]]) -> dict[str, object]:
    for dataset, model_label, exposure_spec, term, scenario in candidates:
        matched = rows.loc[
            (rows["dataset"] == dataset)
            & (rows["model_label"] == model_label)
            & (rows["exposure_spec"] == exposure_spec)
            & (rows["term"] == term)
        ]
        if len(matched) == 1:
            row = matched.iloc[0]
            return {
                "rr_scenario": scenario,
                "dataset": dataset,
                "model_label": model_label,
                "exposure_spec": exposure_spec,
                "term": term,
                "hazard_ratio": float(row["hazard_ratio"]),
                "ci_lower": float(row["ci_lower"]),
                "ci_upper": float(row["ci_upper"]),
                "p_value": float(row["p_value"]),
            }
    labels = [" / ".join(candidate[:4]) for candidate in candidates]
    stop("Unable to identify refined HR", "Could not identify the required insufficient_msa HR. Tried: " + "; ".join(labels))
    raise AssertionError("unreachable")


def read_hr_inputs() -> tuple[dict[str, object], dict[str, object]]:
    required_columns(REFINED_COX, ["dataset", "model_label", "exposure_spec", "term", "hazard_ratio", "ci_lower", "ci_upper", "p_value"])
    rows = pd.read_csv(REFINED_COX)
    main = choose_hr(
        rows,
        [
            ("main", "Model D strata sex year", "Guideline", "1.insufficient_msa", "main_strata_sex_year"),
            ("main", "Model C strata year", "Guideline", "1.insufficient_msa", "main_strata_year"),
        ],
    )
    lag24 = choose_hr(
        rows,
        [
            ("lag24", "Model E lag24 strata sex year", "Guideline", "1.insufficient_msa", "lag24_strata_sex_year"),
            ("lag24", "Model E lag24 age time", "Guideline", "1.insufficient_msa", "lag24_age_time"),
        ],
    )
    return main, lag24


def read_reviewer_premature_hr_inputs() -> list[dict[str, object]]:
    if not REVIEWER_COX.exists():
        return []
    required_columns(
        REVIEWER_COX,
        ["scenario", "model_label", "analysis_population", "design_type", "term", "hazard_ratio", "ci_lower", "ci_upper", "status", "notes"],
    )
    rows = pd.read_csv(REVIEWER_COX)
    rows = rows.loc[rows["status"].eq("completed")].copy()
    for col in ["hazard_ratio", "ci_lower", "ci_upper"]:
        rows[col] = pd.to_numeric(rows[col], errors="coerce")

    def pick(candidates: list[str], output_scenario: str, output_note: str) -> dict[str, object] | None:
        for candidate in candidates:
            matched = rows.loc[rows["scenario"].eq(candidate)].dropna(subset=["hazard_ratio", "ci_lower", "ci_upper"])
            if not matched.empty:
                row = matched.iloc[0]
                return {
                    "scenario": output_scenario,
                    "analysis_population": row["analysis_population"],
                    "exposure": "insufficient_msa",
                    "hr": float(row["hazard_ratio"]),
                    "ci_lower": float(row["ci_lower"]),
                    "ci_upper": float(row["ci_upper"]),
                    "source_model": f"{row['scenario']} / {row['model_label']} / {row['design_type']} / {row['term']}",
                    "notes": output_note,
                }
        return None

    picked = [
        pick(
            ["target_30_69_svy", "target_30_69_current"],
            "main_hr_target_30_69",
            "Reviewer-response primary HR: baseline adults aged 30-69, censored at age 70; Taylor design SE preferred when available.",
        ),
        pick(
            ["target_30_69_lag24"],
            "lag24_hr_target_30_69",
            "Reviewer-response lagged sensitivity HR: baseline adults aged 30-69, censored at age 70; excludes deaths in first 24 months.",
        ),
    ]
    return [row for row in picked if row is not None]


def write_hr_inputs_file(main_hr: dict[str, object], lag_hr: dict[str, object]) -> pd.DataFrame:
    rows = []
    reviewer_rows = read_reviewer_premature_hr_inputs()
    rows.extend(reviewer_rows)
    for scenario, hr in [("main_hr_adult_refined", main_hr), ("lag24_hr_adult_refined", lag_hr)]:
        rows.append(
            {
                "scenario": scenario,
                "analysis_population": "adult_refined_survival_hr_applied_to_premature_30_69",
                "exposure": "insufficient_msa",
                "hr": hr["hazard_ratio"],
                "ci_lower": hr["ci_lower"],
                "ci_upper": hr["ci_upper"],
                "source_model": f"{hr['dataset']} / {hr['model_label']} / {hr['exposure_spec']} / {hr['term']}",
                "notes": "Existing validated adult refined Cox HR retained as a comparison sensitivity for the premature 30-69 burden analysis.",
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(HR_INPUTS_OUT, index=False)
    return out


def read_hr_inputs_for_premature() -> list[dict[str, object]]:
    required_columns(HR_INPUTS_OUT, ["scenario", "analysis_population", "exposure", "hr", "ci_lower", "ci_upper", "source_model", "notes"])
    rows = pd.read_csv(HR_INPUTS_OUT)
    if rows.empty:
        stop("Missing premature HR input rows", "`outputs/tables/hr_inputs_for_burden.csv` has no HR rows.")
    hr_inputs = []
    for _, row in rows.iterrows():
        hr_inputs.append(
            {
                "rr_scenario": row["scenario"],
                "dataset": row["analysis_population"],
                "model_label": row["source_model"],
                "exposure_spec": row["exposure"],
                "term": "1.insufficient_msa",
                "hazard_ratio": float(row["hr"]),
                "ci_lower": float(row["ci_lower"]),
                "ci_upper": float(row["ci_upper"]),
                "p_value": np.nan,
            }
        )
    return hr_inputs


def paf(prevalence: pd.Series | float, hr: float) -> pd.Series | float:
    return prevalence * (hr - 1.0) / (prevalence * (hr - 1.0) + 1.0)


def build_paf(prevalence: pd.DataFrame, hr_inputs: list[dict[str, object]]) -> pd.DataFrame:
    rows = []
    for hr in hr_inputs:
        for _, prev in prevalence.iterrows():
            p = float(prev["prevalence_insufficient_msa"])
            rows.append(
                {
                    **prev.to_dict(),
                    "rr_scenario": hr["rr_scenario"],
                    "hr_dataset": hr["dataset"],
                    "hr_model_label": hr["model_label"],
                    "hr_exposure_spec": hr["exposure_spec"],
                    "hr_term": hr["term"],
                    "hazard_ratio": hr["hazard_ratio"],
                    "ci_lower": hr["ci_lower"],
                    "ci_upper": hr["ci_upper"],
                    "p_value": hr["p_value"],
                    "paf": paf(p, float(hr["hazard_ratio"])),
                }
            )
    return pd.DataFrame(rows)


def build_paf_mc(prevalence: pd.DataFrame, hr_inputs: list[dict[str, object]]) -> pd.DataFrame:
    rng = np.random.default_rng(RNG_SEED)
    rows = []
    for hr in hr_inputs:
        log_hr = math.log(float(hr["hazard_ratio"]))
        se_log_hr = (math.log(float(hr["ci_upper"])) - math.log(float(hr["ci_lower"]))) / (2 * 1.96)
        hr_draws = np.exp(rng.normal(log_hr, se_log_hr, size=N_DRAWS))
        for _, prev in prevalence.iterrows():
            p = float(prev["prevalence_insufficient_msa"])
            paf_draws = p * (hr_draws - 1.0) / (p * (hr_draws - 1.0) + 1.0)
            row = prev.to_dict()
            row.update(
                {
                    "rr_scenario": hr["rr_scenario"],
                    "hr_dataset": hr["dataset"],
                    "hr_model_label": hr["model_label"],
                    "hazard_ratio": hr["hazard_ratio"],
                    "ci_lower": hr["ci_lower"],
                    "ci_upper": hr["ci_upper"],
                    "se_log_hr": se_log_hr,
                    "n_draws": N_DRAWS,
                    "paf_median": float(np.quantile(paf_draws, 0.5)),
                    "paf_p2_5": float(np.quantile(paf_draws, 0.025)),
                    "paf_p97_5": float(np.quantile(paf_draws, 0.975)),
                }
            )
            rows.append(row)
    return pd.DataFrame(rows)


def premature_common(row: pd.Series, stratum: str, age_group: str, sex: str) -> dict[str, object]:
    return {
        "target_period": PREMATURE_PERIOD,
        "target_period_label": "NHIS 2024 premature mortality age 30-69 prevalence",
        "period_role": "preferred main premature mortality prevalence",
        "main_present_day_prevalence": 1,
        "period_start_year": 2024,
        "period_end_year": 2024,
        "years_included": "2024",
        "analysis_population": "premature_30_69",
        "stratum": stratum,
        "year": "all",
        "age_group": age_group,
        "sex": sex,
        "n_unweighted": int(row["n_unweighted"]) if pd.notna(row.get("n_unweighted")) else np.nan,
        "n_exposed": np.nan,
        "weighted_total": float(row["weighted_total"]) if pd.notna(row.get("weighted_total")) else np.nan,
        "weighted_exposed": float(row["weighted_insufficient_msa"]) if pd.notna(row.get("weighted_insufficient_msa")) else np.nan,
        "prevalence_meets_msa_guideline": float(row["prevalence_meets_msa_guideline"]),
        "prevalence_insufficient_msa": float(row["prevalence_insufficient_msa"]),
    }


def read_premature_prevalence_tables() -> pd.DataFrame:
    required = ["n_unweighted", "weighted_total", "weighted_insufficient_msa", "prevalence_meets_msa_guideline", "prevalence_insufficient_msa"]
    frames: list[dict[str, object]] = []
    specs = [
        (NHIS2024_PREMATURE_OVERALL, "overall", "all", "all", []),
        (NHIS2024_PREMATURE_SEX, "sex", "all", None, ["sex"]),
        (NHIS2024_PREMATURE_AGE, "age_group", None, "all", ["age_group"]),
        (NHIS2024_PREMATURE_AGE_SEX, "age_group_sex", None, None, ["age_group", "sex"]),
    ]
    for path, stratum, fixed_age, fixed_sex, extras in specs:
        if not path.exists():
            stop(
                "Missing NHIS 2024 premature prevalence output",
                f"`{path.relative_to(PROJECT_ROOT)}` is missing. Run `python code/python/08_build_nhis_2024_msa_prevalence.py` first.",
            )
        cols = pd.read_csv(path, nrows=0).columns.tolist()
        missing = [col for col in required + extras if col not in cols]
        if missing:
            stop("Malformed premature prevalence output", f"`{path.relative_to(PROJECT_ROOT)}` is missing columns: {', '.join(missing)}.")
        df = pd.read_csv(path)
        for _, row in df.iterrows():
            age_group = fixed_age if fixed_age is not None else str(row["age_group"])
            sex = fixed_sex if fixed_sex is not None else str(row["sex"])
            frames.append(premature_common(row, stratum, age_group, sex))
    out = pd.DataFrame(frames)
    expected = {"30-34", "35-44", "45-54", "55-64", "65-69"}
    found = set(out.loc[out["stratum"] == "age_group", "age_group"])
    if found != expected:
        stop("Unexpected premature age groups in prevalence", f"Expected {sorted(expected)}, found {sorted(found)}.")
    return out.sort_values(["stratum", "age_group", "sex"]).reset_index(drop=True)


def build_premature_30_69_paf_outputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    prevalence = read_premature_prevalence_tables()
    hr_inputs = read_hr_inputs_for_premature()
    paf_rows = build_paf(prevalence, hr_inputs)
    paf_mc = build_paf_mc(prevalence, hr_inputs)
    paf_rows.to_csv(PAF_PREMATURE_OUT, index=False)
    paf_mc.to_csv(PAF_MC_PREMATURE_OUT, index=False)
    return paf_rows, paf_mc


def find_external_csv(required: list[str], keywords: list[str]) -> Path | None:
    for path in sorted(EXTERNAL_DIR.glob("*.csv")):
        name = path.name.lower()
        if "template" in name:
            continue
        if keywords and not any(keyword in name for keyword in keywords):
            continue
        try:
            cols = pd.read_csv(path, nrows=0).columns.tolist()
        except Exception:
            continue
        if all(col in cols for col in required):
            return path
    return None


def aggregate_from_age_sex(rows: pd.DataFrame, value_col: str) -> pd.DataFrame:
    out = [rows.copy()]
    overall = rows.groupby(["rr_scenario"], as_index=False)[value_col].sum()
    overall["stratum"] = "overall"
    overall["year"] = "all"
    overall["age_group"] = "all"
    overall["sex"] = "all"
    out.append(overall[["rr_scenario", "stratum", "year", "age_group", "sex", value_col]])

    by_age = rows.groupby(["rr_scenario", "age_group"], as_index=False)[value_col].sum()
    by_age["stratum"] = "age_group"
    by_age["year"] = "all"
    by_age["sex"] = "all"
    out.append(by_age[["rr_scenario", "stratum", "year", "age_group", "sex", value_col]])

    by_sex = rows.groupby(["rr_scenario", "sex"], as_index=False)[value_col].sum()
    by_sex["stratum"] = "sex"
    by_sex["year"] = "all"
    by_sex["age_group"] = "all"
    out.append(by_sex[["rr_scenario", "stratum", "year", "age_group", "sex", value_col]])

    return pd.concat(out, ignore_index=True)


def maybe_compute_deaths(paf_rows: pd.DataFrame) -> tuple[Path | None, pd.DataFrame | None]:
    required = ["year", "sex", "age_group", "deaths_allcause", "source", "notes"]
    death_file = find_external_csv(required, ["death", "mortality"])
    if death_file is None:
        append_issue_once(
            "Missing external all-cause death counts",
            "No non-template CSV in `data/external/` contained official all-cause deaths by `year`, `sex`, and `age_group`. "
            "`data/external/us_allcause_deaths_template.csv` and `docs/external_mortality_data_needed.md` were created. "
            "Attributable deaths were not computed.",
        )
        return None, None

    deaths = pd.read_csv(death_file)
    deaths["deaths_allcause"] = pd.to_numeric(deaths["deaths_allcause"], errors="coerce")
    if deaths["deaths_allcause"].isna().any():
        stop("Invalid external deaths", f"`{death_file}` contains non-numeric deaths_allcause values.")

    age_sex_paf = paf_rows.loc[paf_rows["stratum"] == "age_group_sex"].copy()
    merged = deaths.merge(
        age_sex_paf[["rr_scenario", "age_group", "sex", "paf"]],
        on=["age_group", "sex"],
        how="inner",
    )
    if merged.empty:
        append_issue_once(
            "External deaths did not match burden strata",
            f"`{death_file}` was found, but no rows matched `age_group` and `sex` values in the PAF table. Attributable deaths were not computed.",
        )
        return death_file, None

    merged["attributable_deaths"] = merged["paf"] * merged["deaths_allcause"]
    age_sex = merged[["rr_scenario", "year", "age_group", "sex", "deaths_allcause", "paf", "attributable_deaths", "source", "notes"]].copy()
    age_sex["stratum"] = "age_group_sex"
    summary = aggregate_from_age_sex(age_sex[["rr_scenario", "stratum", "year", "age_group", "sex", "attributable_deaths"]], "attributable_deaths")
    result = pd.concat([age_sex, summary], ignore_index=True, sort=False)
    write_csv_preserve_existing(result, DEATHS_OUT, preserve_existing=True)
    return death_file, result


def maybe_compute_yll(death_rows: pd.DataFrame | None) -> Path | None:
    required = ["year", "sex", "age_group", "remaining_life_expectancy", "source", "notes"]
    life_file = find_external_csv(required, ["life", "table", "expectancy"])
    if life_file is None:
        append_issue_once(
            "Missing external life table inputs",
            "No non-template CSV in `data/external/` contained remaining life expectancy by `year`, `sex`, and `age_group`. "
            "`data/external/us_life_table_template.csv` and `docs/external_life_table_data_needed.md` were created. YLL was not computed.",
        )
        return None
    if death_rows is None:
        append_issue_once("YLL skipped because deaths missing", "Life table inputs may exist, but attributable deaths were not available; YLL was not computed.")
        return life_file

    life = pd.read_csv(life_file)
    life["remaining_life_expectancy"] = pd.to_numeric(life["remaining_life_expectancy"], errors="coerce")
    if life["remaining_life_expectancy"].isna().any():
        stop("Invalid life table inputs", f"`{life_file}` contains non-numeric remaining_life_expectancy values.")

    age_sex_deaths = death_rows.loc[death_rows["stratum"] == "age_group_sex"].copy()
    merged = age_sex_deaths.merge(
        life[["year", "sex", "age_group", "remaining_life_expectancy", "source", "notes"]],
        on=["year", "sex", "age_group"],
        how="inner",
        suffixes=("", "_life_table"),
    )
    if merged.empty:
        append_issue_once(
            "Life table inputs did not match death strata",
            f"`{life_file}` was found, but no rows matched attributable death rows on `year`, `sex`, and `age_group`. YLL was not computed.",
        )
        return life_file

    merged["yll"] = merged["attributable_deaths"] * merged["remaining_life_expectancy"]
    age_sex = merged[["rr_scenario", "year", "age_group", "sex", "attributable_deaths", "remaining_life_expectancy", "yll", "source", "notes"]].copy()
    age_sex["stratum"] = "age_group_sex"
    summary = aggregate_from_age_sex(age_sex[["rr_scenario", "stratum", "year", "age_group", "sex", "yll"]], "yll")
    result = pd.concat([age_sex, summary], ignore_index=True, sort=False)
    write_csv_preserve_existing(result, YLL_OUT, preserve_existing=True)
    return life_file


def check_productivity_inputs() -> Path | None:
    required = [
        "year",
        "sex",
        "age_group",
        "employment_rate",
        "annual_earnings",
        "productive_years_remaining",
        "gdp_per_employed_person",
        "source",
        "notes",
    ]
    productivity_file = find_external_csv(required, ["productivity", "earnings", "employment"])
    if productivity_file is None:
        append_issue_once(
            "Missing external productivity inputs",
            "No non-template CSV in `data/external/` contained the documented productivity input columns. "
            "`data/external/us_productivity_inputs_template.csv` and `docs/external_productivity_data_needed.md` were created. "
            "Productivity losses were not computed.",
        )
        return None
    append_issue_once(
        "Productivity inputs detected but cost framework not finalized",
        f"`{productivity_file}` was detected, but final productivity losses require an explicitly documented cost framework. "
        "The current script does not compute final productivity costs.",
    )
    return productivity_file


def nhis2024_section(
    nhis2024_summary: dict[str, float] | None,
    paf_by_period: pd.DataFrame,
    paf_mc_by_period: pd.DataFrame,
    main_hr: dict[str, object],
) -> str:
    if nhis2024_summary is None or NHIS2024_PERIOD not in set(paf_by_period["target_period"]):
        return (
            "NHIS 2024 current prevalence was not available in this run. "
            "Run `python code/python/07_download_nhis_2024_prevalence.py` and "
            "`python code/python/08_build_nhis_2024_msa_prevalence.py`, then rerun this burden script."
        )
    paf_row = paf_by_period.loc[
        (paf_by_period["target_period"] == NHIS2024_PERIOD)
        & (paf_by_period["stratum"] == "overall")
        & (paf_by_period["rr_scenario"] == main_hr["rr_scenario"])
    ].iloc[0]
    mc_row = paf_mc_by_period.loc[
        (paf_mc_by_period["target_period"] == NHIS2024_PERIOD)
        & (paf_mc_by_period["stratum"] == "overall")
        & (paf_mc_by_period["rr_scenario"] == main_hr["rr_scenario"])
    ].iloc[0]
    return f"""- NHIS 2024 source used: `{nhis2024_summary.get("source", "unknown")}`
- NHIS 2024 weighted prevalence meeting MSA guideline: {float(nhis2024_summary["prevalence_meets_msa_guideline"]):.4f}
- NHIS 2024 weighted prevalence insufficient MSA: {float(nhis2024_summary["prevalence_insufficient_msa"]):.4f}
- PAF using NHIS 2024 prevalence and the main HR: {float(paf_row["paf"]):.4f}
- Monte Carlo PAF median: {float(mc_row["paf_median"]):.4f}
- Monte Carlo PAF 95% interval: {float(mc_row["paf_p2_5"]):.4f}-{float(mc_row["paf_p97_5"]):.4f}
- Comparison with full pooled 1997-2018 PAF: NHIS 2024 gives {float(paf_row["paf"]):.4f}; full pooled gives {float(paf_by_period.loc[(paf_by_period["target_period"] == "full_pooled_1997_2018") & (paf_by_period["stratum"] == "overall") & (paf_by_period["rr_scenario"] == main_hr["rr_scenario"]), "paf"].iloc[0]):.4f}.
- Limitation: NHIS 2024 is used only for contemporary exposure prevalence. It is not used to estimate prospective mortality HRs."""


def write_readiness_report(
    prevalence: pd.DataFrame,
    prevalence_by_period: pd.DataFrame,
    paf_rows: pd.DataFrame,
    paf_by_period: pd.DataFrame,
    paf_mc: pd.DataFrame,
    paf_mc_by_period: pd.DataFrame,
    nhis2024_summary: dict[str, float] | None,
    main_hr: dict[str, object],
    lag_hr: dict[str, object],
    counts: dict[str, int],
    death_file: Path | None,
    death_rows: pd.DataFrame | None,
    life_file: Path | None,
    productivity_file: Path | None,
) -> None:
    overall_prev = prevalence.loc[prevalence["stratum"] == "overall"].iloc[0]
    overall_paf = paf_rows.loc[(paf_rows["stratum"] == "overall") & (paf_rows["rr_scenario"] == main_hr["rr_scenario"])].iloc[0]
    overall_mc = paf_mc.loc[(paf_mc["stratum"] == "overall") & (paf_mc["rr_scenario"] == main_hr["rr_scenario"])].iloc[0]
    preferred_period = NHIS2024_PERIOD if NHIS2024_PERIOD in set(prevalence_by_period["target_period"]) else MAIN_PRESENT_DAY_PERIOD
    main_period_prev = prevalence_by_period.loc[
        (prevalence_by_period["target_period"] == preferred_period) & (prevalence_by_period["stratum"] == "overall")
    ].iloc[0]
    main_period_paf = paf_by_period.loc[
        (paf_by_period["target_period"] == preferred_period)
        & (paf_by_period["stratum"] == "overall")
        & (paf_by_period["rr_scenario"] == main_hr["rr_scenario"])
    ].iloc[0]
    main_period_mc = paf_mc_by_period.loc[
        (paf_mc_by_period["target_period"] == preferred_period)
        & (paf_mc_by_period["stratum"] == "overall")
        & (paf_mc_by_period["rr_scenario"] == main_hr["rr_scenario"])
    ].iloc[0]
    recent_period_paf = paf_by_period.loc[
        (paf_by_period["target_period"] == MAIN_PRESENT_DAY_PERIOD)
        & (paf_by_period["stratum"] == "overall")
        & (paf_by_period["rr_scenario"] == main_hr["rr_scenario"])
    ].iloc[0]

    period_lines = []
    period_overall = prevalence_by_period.loc[prevalence_by_period["stratum"] == "overall"].copy()
    for _, row in period_overall.iterrows():
        period_paf = paf_by_period.loc[
            (paf_by_period["target_period"] == row["target_period"])
            & (paf_by_period["stratum"] == "overall")
            & (paf_by_period["rr_scenario"] == main_hr["rr_scenario"])
        ].iloc[0]
        period_lines.append(
            f"- `{row['target_period']}` ({row['years_included']}): prevalence {float(row['prevalence_insufficient_msa']):.4f}; "
            f"main-HR PAF {float(period_paf['paf']):.4f}"
        )

    produced = [PREVALENCE_OUT, PAF_OUT, PAF_MC_OUT, PREVALENCE_PERIOD_OUT, PAF_PERIOD_OUT, PAF_MC_PERIOD_OUT, READINESS_OUT]
    if HR_INPUTS_OUT.exists():
        produced.append(HR_INPUTS_OUT)
    if PAF_NHIS2024_OUT.exists():
        produced.append(PAF_NHIS2024_OUT)
    if PAF_MC_NHIS2024_OUT.exists():
        produced.append(PAF_MC_NHIS2024_OUT)
    if PAF_PREMATURE_OUT.exists():
        produced.append(PAF_PREMATURE_OUT)
    if PAF_MC_PREMATURE_OUT.exists():
        produced.append(PAF_MC_PREMATURE_OUT)
    if death_rows is not None and DEATHS_OUT.exists():
        produced.append(DEATHS_OUT)
    if YLL_OUT.exists():
        produced.append(YLL_OUT)
    if PRODUCTIVITY_OUT.exists():
        produced.append(PRODUCTIVITY_OUT)

    text = f"""# Burden readiness report

Generated by `code/python/06_burden_paf_deaths_yll.py` on {datetime.now().isoformat(timespec="seconds")}.

These estimates are preliminary comparative-risk estimates under the modelled
counterfactual that insufficient MSA is shifted to meeting the MSA guideline.
They should not be interpreted as proof of a direct causal effect.

## HR input

- All-adult comparison HR used for the legacy/current-prevalence section: {float(main_hr["hazard_ratio"]):.3f} ({float(main_hr["ci_lower"]):.3f}-{float(main_hr["ci_upper"]):.3f})
- Selected refined model: `{main_hr["dataset"]}` / `{main_hr["model_label"]}` / `{main_hr["exposure_spec"]}` / `{main_hr["term"]}`
- Lag-24 sensitivity HR: {float(lag_hr["hazard_ratio"]):.3f} ({float(lag_hr["ci_lower"]):.3f}-{float(lag_hr["ci_upper"]):.3f})
- Lag-24 sensitivity model: `{lag_hr["dataset"]}` / `{lag_hr["model_label"]}` / `{lag_hr["exposure_spec"]}` / `{lag_hr["term"]}`

## Prevalence and PAF

- Rows read from full processed dataset: {counts["rows_read"]:,}
- Adult sample rows before MSA/weight restrictions: {counts["sample_adult_18plus"]:,}
- Rows used for prevalence: {counts["eligible_for_prevalence"]:,}
- Prevalence weight: `weight_sample_adult` (`SAMPWEIGHT`), not `weight_mortality`.
- Preferred present-day prevalence period: `{preferred_period}`.
- Rationale: NHIS 2024 is preferred when available because it is the most recent current-prevalence input. The HR still comes from NHIS-LMF 1997-2018 because NHIS 2024 does not yet provide sufficient linked mortality follow-up for prospective Cox models.
- Overall weighted prevalence of insufficient MSA for `{preferred_period}`: {float(main_period_prev["prevalence_insufficient_msa"]):.4f}
- Overall PAF for `{preferred_period}` using the main HR: {float(main_period_paf["paf"]):.4f}
- Monte Carlo PAF median for `{preferred_period}`: {float(main_period_mc["paf_median"]):.4f}
- Monte Carlo PAF 95% interval for `{preferred_period}`: {float(main_period_mc["paf_p2_5"]):.4f}-{float(main_period_mc["paf_p97_5"]):.4f}
- Recent pooled 2015-2018 PAF: {float(recent_period_paf["paf"]):.4f}; this is now a sensitivity if NHIS 2024 is available.
- Full pooled 1997-2018 prevalence: {float(overall_prev["prevalence_insufficient_msa"]):.4f}; full pooled PAF: {float(overall_paf["paf"]):.4f}; this should be treated as historical sensitivity, not the main present-day burden input.
- Full pooled Monte Carlo PAF median: {float(overall_mc["paf_median"]):.4f}; 95% interval: {float(overall_mc["paf_p2_5"]):.4f}-{float(overall_mc["paf_p97_5"]):.4f}.
- Monte Carlo draws: {N_DRAWS:,}; prevalence uncertainty is not yet included.

## Target-period prevalence and PAF

{chr(10).join(period_lines)}

Pooled 1997-2018 should be treated as a sensitivity analysis because it blends
older MSA prevalence patterns with later survey years. When NHIS 2024 is
available, it is the preferred current-prevalence input for present-day burden.
The recent pooled 2015-2018 and latest-year-only 2018 estimates are retained as
historical sensitivity checks.

Age-sex-specific PAFs are available in
`outputs/tables/msa_paf_insufficient_by_period.csv` for linkage to external
all-cause death counts once official death inputs are supplied.

## NHIS 2024 current prevalence scenario

{nhis2024_section(nhis2024_summary, paf_by_period, paf_mc_by_period, main_hr)}

## Premature mortality 30-69 PAF scenario

- Main manuscript burden population: deaths occurring between ages 30 and 69 years.
- HR source: reviewer-response target-population Cox HR for `insufficient_msa`
  among baseline adults aged 30-69 years, censored at age 70; adult refined HRs
  are retained as comparison sensitivities.
- Exact NHIS 2024 age groups: 30-34, 35-44, 45-54, 55-64, and 65-69.
- PAF outputs:
  - `outputs/tables/msa_paf_insufficient_premature_30_69_nhis2024.csv`
  - `outputs/tables/msa_paf_insufficient_montecarlo_premature_30_69_nhis2024.csv`
- HR input file: `outputs/tables/hr_inputs_for_burden.csv`

## External inputs

- External all-cause death counts available: {"yes, `" + death_file.name + "`" if death_file else "no"}
- Life table inputs available: {"yes, `" + life_file.name + "`" if life_file else "no"}
- Productivity inputs available: {"yes, `" + productivity_file.name + "`" if productivity_file else "no"}

## Outputs produced

{chr(10).join("- `" + str(path.relative_to(PROJECT_ROOT)).replace(chr(92), "/") + "`" for path in produced)}

## Still needed before final burden estimates

- Official all-cause death counts by year, sex, and age group if attributable deaths are required.
- Official remaining life expectancy by year, sex, and age group if YLL is required.
- A documented productivity-cost framework and external productivity inputs before productivity losses are reported.
- Survey-based prevalence uncertainty if final uncertainty intervals should include exposure-prevalence sampling variability.
- Sensitivity analyses using lag24 HRs and the 0-1 versus 2-4 times/week optimal-range contrast.

## Status

The PAF outputs are preliminary and model-based. Attributable deaths and YLL are
only produced when external official inputs are present. Life expectancy gains
were not computed because that requires a separate life-table framework.
"""
    READINESS_OUT.write_text(text, encoding="utf-8")


def main() -> None:
    ensure_dirs()
    create_external_templates()

    if not DECISION_REPORT.exists():
        append_issue_once("Missing refined decision report", "`outputs/tables/refined_cox_decision_report.md` was not found. Proceeding from refined Cox CSV only.")

    prevalence_frame, counts = read_prevalence_frame()
    prevalence = build_prevalence(prevalence_frame)
    write_csv_preserve_existing(prevalence, PREVALENCE_OUT, preserve_existing=True)
    target_periods = define_target_periods(prevalence_frame)
    prevalence_by_period = build_prevalence_by_period(prevalence_frame, target_periods)
    nhis2024_prevalence, nhis2024_summary = build_nhis2024_period_prevalence()
    if nhis2024_prevalence is not None:
        prevalence_by_period["main_present_day_prevalence"] = 0
        prevalence_by_period = pd.concat([prevalence_by_period, nhis2024_prevalence], ignore_index=True, sort=False)
    write_csv_preserve_existing(prevalence_by_period, PREVALENCE_PERIOD_OUT, preserve_existing=True)

    main_hr, lag_hr = read_hr_inputs()
    write_hr_inputs_file(main_hr, lag_hr)
    paf_rows = build_paf(prevalence, [main_hr, lag_hr])
    write_csv_preserve_existing(paf_rows, PAF_OUT, preserve_existing=True)
    paf_by_period = build_paf(prevalence_by_period, [main_hr, lag_hr])
    write_csv_preserve_existing(paf_by_period, PAF_PERIOD_OUT, preserve_existing=True)
    if nhis2024_prevalence is not None:
        write_csv_preserve_existing(
            paf_by_period.loc[paf_by_period["target_period"] == NHIS2024_PERIOD],
            PAF_NHIS2024_OUT,
            preserve_existing=True,
        )

    paf_mc = build_paf_mc(prevalence, [main_hr, lag_hr])
    write_csv_preserve_existing(paf_mc, PAF_MC_OUT, preserve_existing=True)
    paf_mc_by_period = build_paf_mc(prevalence_by_period, [main_hr, lag_hr])
    write_csv_preserve_existing(paf_mc_by_period, PAF_MC_PERIOD_OUT, preserve_existing=True)
    if nhis2024_prevalence is not None:
        write_csv_preserve_existing(
            paf_mc_by_period.loc[paf_mc_by_period["target_period"] == NHIS2024_PERIOD],
            PAF_MC_NHIS2024_OUT,
            preserve_existing=True,
        )

    premature_paf_rows, premature_paf_mc = build_premature_30_69_paf_outputs()

    preferred_period = NHIS2024_PERIOD if nhis2024_prevalence is not None else MAIN_PRESENT_DAY_PERIOD
    main_period_paf_rows = paf_by_period.loc[paf_by_period["target_period"] == preferred_period].copy()
    death_file, death_rows = maybe_compute_deaths(main_period_paf_rows)
    life_file = maybe_compute_yll(death_rows)
    productivity_file = check_productivity_inputs()

    write_readiness_report(
        prevalence,
        prevalence_by_period,
        paf_rows,
        paf_by_period,
        paf_mc,
        paf_mc_by_period,
        nhis2024_summary,
        main_hr,
        lag_hr,
        counts,
        death_file,
        death_rows,
        life_file,
        productivity_file,
    )

    append_issue_once(
        "Burden prevalence denominator limitation",
        "Prevalence was estimated from `data/processed/msa_survival_full.csv`, which is the processed survival dataset. "
        "This estimates prevalence in the adult sample rows retained in the processed survival file, using `weight_sample_adult`; "
        "confirm whether final burden estimates should instead use all raw NHIS sample-adult respondents regardless of mortality linkage eligibility.",
    )
    append_issue_once(
        "Present-day burden prevalence period limitation",
        "The burden pipeline estimates full pooled 1997-2018, recent pooled 2015-2018, latest-year-only prevalence, and NHIS 2024 current prevalence when the NHIS 2024 processed file exists. "
        "NHIS 2024 is preferred for current prevalence, while 2015-2018 and 1997-2018 remain sensitivity scenarios. "
        "Confirm this prevalence-period choice before final burden estimates.",
    )

    log_lines = [
        f"Burden pipeline run at: {datetime.now().isoformat(timespec='seconds')}",
        f"Prevalence rows used: {counts['eligible_for_prevalence']}",
        f"Main HR: {main_hr['hazard_ratio']}",
        f"Lag24 HR: {lag_hr['hazard_ratio']}",
        f"Created: {PREVALENCE_OUT.relative_to(PROJECT_ROOT)}",
        f"Created: {PAF_OUT.relative_to(PROJECT_ROOT)}",
        f"Created: {PAF_MC_OUT.relative_to(PROJECT_ROOT)}",
        f"Created: {PREVALENCE_PERIOD_OUT.relative_to(PROJECT_ROOT)}",
        f"Created: {PAF_PERIOD_OUT.relative_to(PROJECT_ROOT)}",
        f"Created: {PAF_MC_PERIOD_OUT.relative_to(PROJECT_ROOT)}",
        f"Created: {HR_INPUTS_OUT.relative_to(PROJECT_ROOT)}",
        f"Created: {PAF_PREMATURE_OUT.relative_to(PROJECT_ROOT)}",
        f"Created: {PAF_MC_PREMATURE_OUT.relative_to(PROJECT_ROOT)}",
        f"NHIS 2024 prevalence scenario used: {nhis2024_prevalence is not None}",
        f"Created: {READINESS_OUT.relative_to(PROJECT_ROOT)}",
    ]
    RUN_LOG.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    print("\n".join(log_lines))


if __name__ == "__main__":
    main()
