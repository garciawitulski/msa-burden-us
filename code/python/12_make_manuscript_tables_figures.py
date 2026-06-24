"""Create manuscript-ready tables for the MSA burden US project.

This script formats existing survival, prevalence, PAF, deaths, YLL, and
optional downstream counterfactual outputs. It does not run new models and does
not calculate productivity losses or costs. Manuscript figures are rendered by
the R scripts in `code/r/figures/`.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TABLE_DIR = PROJECT_ROOT / "outputs/tables"
MANUSCRIPT_TABLE_DIR = TABLE_DIR / "manuscript"
PROCESSED_DIR = PROJECT_ROOT / "data/processed"

REFINED_COX = TABLE_DIR / "refined_cox_msa_allcause.csv"
REFINED_DECISION = TABLE_DIR / "refined_cox_decision_report.md"
PAF_2024 = TABLE_DIR / "msa_paf_insufficient_using_nhis2024.csv"
PAF_PREMATURE = TABLE_DIR / "msa_paf_insufficient_premature_30_69_nhis2024.csv"
ATTR_DEATHS = TABLE_DIR / "msa_attributable_deaths_nhis2024.csv"
ATTR_DEATHS_PREMATURE = TABLE_DIR / "msa_attributable_deaths_premature_30_69_nhis2024.csv"
YLL = TABLE_DIR / "msa_yll_nhis2024.csv"
YLL_PREMATURE = TABLE_DIR / "msa_yll_premature_30_69_nhis2024.csv"
BURDEN_SUMMARY = TABLE_DIR / "msa_burden_summary_nhis2024.csv"
BURDEN_SUMMARY_PREMATURE = TABLE_DIR / "msa_burden_summary_premature_30_69_nhis2024.csv"
RECONCILIATION = TABLE_DIR / "msa_burden_reconciliation_nhis2024.csv"
RECONCILIATION_PREMATURE = TABLE_DIR / "msa_burden_reconciliation_premature_30_69.csv"
CONTRIBUTIONS = TABLE_DIR / "msa_burden_contributions_by_age_sex.csv"
CONTRIBUTIONS_PREMATURE = TABLE_DIR / "msa_burden_contributions_by_age_sex_premature_30_69.csv"
NHIS2024_OVERALL = TABLE_DIR / "nhis_2024_msa_prevalence_overall.csv"
NHIS2024_AGE_SEX = TABLE_DIR / "nhis_2024_msa_prevalence_by_age_sex.csv"
NHIS2024_PREMATURE_OVERALL = TABLE_DIR / "nhis_2024_msa_prevalence_premature_30_69_overall.csv"
NHIS2024_PREMATURE_AGE_SEX = TABLE_DIR / "nhis_2024_msa_prevalence_premature_30_69_by_age_sex.csv"
HR_INPUTS = TABLE_DIR / "hr_inputs_for_burden.csv"
SURVIVAL_MAIN = PROCESSED_DIR / "msa_survival_main_completecase.csv"

TABLE1_CSV = MANUSCRIPT_TABLE_DIR / "table1_cohort_characteristics.csv"
TABLE1_MD = MANUSCRIPT_TABLE_DIR / "table1_cohort_characteristics.md"
TABLE2_CSV = MANUSCRIPT_TABLE_DIR / "table2_refined_cox_hazard_ratios.csv"
TABLE2_MD = MANUSCRIPT_TABLE_DIR / "table2_refined_cox_hazard_ratios.md"
TABLE3_CSV = MANUSCRIPT_TABLE_DIR / "table3_nhis2024_prevalence_paf.csv"
TABLE3_MD = MANUSCRIPT_TABLE_DIR / "table3_nhis2024_prevalence_paf.md"
TABLE4_CSV = MANUSCRIPT_TABLE_DIR / "table4_attributable_deaths_yll.csv"
TABLE4_MD = MANUSCRIPT_TABLE_DIR / "table4_attributable_deaths_yll.md"
TABLE5_CSV = MANUSCRIPT_TABLE_DIR / "table5_productivity_losses.csv"
TABLE5_MD = MANUSCRIPT_TABLE_DIR / "table5_productivity_losses.md"
TABLES1_CSV = MANUSCRIPT_TABLE_DIR / "supplementary_table_s1_reconciliation.csv"
TABLES1_MD = MANUSCRIPT_TABLE_DIR / "supplementary_table_s1_reconciliation.md"
TABLES2_CSV = MANUSCRIPT_TABLE_DIR / "supplementary_table_s2_lag24_sensitivity.csv"
TABLES2_MD = MANUSCRIPT_TABLE_DIR / "supplementary_table_s2_lag24_sensitivity.md"
TABLES3_CSV = MANUSCRIPT_TABLE_DIR / "supplementary_table_s3_life_expectancy_gain.csv"
TABLES3_MD = MANUSCRIPT_TABLE_DIR / "supplementary_table_s3_life_expectancy_gain.md"
TABLES4_CSV = MANUSCRIPT_TABLE_DIR / "supplementary_table_s4_productivity_losses.csv"
TABLES4_MD = MANUSCRIPT_TABLE_DIR / "supplementary_table_s4_productivity_losses.md"
TABLES5_CSV = MANUSCRIPT_TABLE_DIR / "supplementary_table_s5_all_adult_prevalence_paf.csv"
TABLES5_MD = MANUSCRIPT_TABLE_DIR / "supplementary_table_s5_all_adult_prevalence_paf.md"
TABLES6_CSV = MANUSCRIPT_TABLE_DIR / "supplementary_table_s6_all_adult_attributable_deaths_yll.csv"
TABLES6_MD = MANUSCRIPT_TABLE_DIR / "supplementary_table_s6_all_adult_attributable_deaths_yll.md"
SUMMARY_MD = MANUSCRIPT_TABLE_DIR / "manuscript_results_summary.md"

LIFE_GAIN = TABLE_DIR / "msa_life_expectancy_gain_nhis2024.csv"
LIFE_GAIN_MC = TABLE_DIR / "msa_life_expectancy_gain_montecarlo_nhis2024.csv"
LIFE_GAIN_PREMATURE = TABLE_DIR / "msa_life_expectancy_gain_premature_30_69_nhis2024.csv"
LIFE_GAIN_MC_PREMATURE = TABLE_DIR / "msa_life_expectancy_gain_montecarlo_premature_30_69_nhis2024.csv"
PRODUCTIVITY_TOTAL = TABLE_DIR / "msa_productivity_losses_nhis2024.csv"
PRODUCTIVITY_MC = TABLE_DIR / "msa_productivity_losses_montecarlo_nhis2024.csv"
PRODUCTIVITY_DETAIL = TABLE_DIR / "msa_productivity_losses_by_age_sex_nhis2024.csv"
PRODUCTIVITY_REPORT = TABLE_DIR / "msa_productivity_losses_report.md"
PRODUCTIVITY_TOTAL_PREMATURE = TABLE_DIR / "msa_productivity_losses_premature_30_69_nhis2024.csv"
PRODUCTIVITY_MC_PREMATURE = TABLE_DIR / "msa_productivity_losses_montecarlo_premature_30_69_nhis2024.csv"
PRODUCTIVITY_DETAIL_PREMATURE = TABLE_DIR / "msa_productivity_losses_by_age_sex_premature_30_69_nhis2024.csv"
PRODUCTIVITY_REPORT_PREMATURE = TABLE_DIR / "msa_productivity_losses_report_premature_30_69.md"

PRIMARY_SCENARIO = "main_strata_sex_year"
LAG24_SCENARIO = "lag24_strata_sex_year"
PRIMARY_PREMATURE_SCENARIO = "main_hr_target_30_69"
LAG24_PREMATURE_SCENARIO = "lag24_hr_target_30_69"
MAIN_MODEL_LABEL = "Model D strata sex year"
LAG24_MODEL_LABEL = "Model E lag24 strata sex year"
AGE_ORDER = ["18-34", "35-44", "45-54", "55-64", "65-74", "75+"]
PREMATURE_AGE_ORDER = ["30-34", "35-44", "45-54", "55-64", "65-69"]
SEX_ORDER = ["Female", "Male"]


def ensure_dirs() -> None:
    MANUSCRIPT_TABLE_DIR.mkdir(parents=True, exist_ok=True)


def read_required(path: Path, required: list[str] | None = None) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"Required file not found: {path.relative_to(PROJECT_ROOT)}")
    df = pd.read_csv(path)
    if required:
        missing = [col for col in required if col not in df.columns]
        if missing:
            raise SystemExit(f"{path.relative_to(PROJECT_ROOT)} is missing columns: {', '.join(missing)}")
    return df


def to_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def fmt_int(value: float | int | str | None) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):,.0f}"


def fmt_float(value: float | int | str | None, digits: int = 2) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):.{digits}f}"


def fmt_pct(value: float | int | str | None, digits: int = 1) -> str:
    if pd.isna(value):
        return ""
    return f"{100 * float(value):.{digits}f}"


def fmt_p(value: float | int | str | None) -> str:
    if pd.isna(value) or value == "":
        return ""
    value = float(value)
    if value < 0.001:
        return "<0.001"
    return f"{value:.3f}"


def fmt_hr_ci(hr: float, lo: float, hi: float) -> str:
    return f"{hr:.3f} ({lo:.3f}-{hi:.3f})"


def fmt_interval(point: float, lo: float, hi: float) -> str:
    return f"{fmt_int(point)} ({fmt_int(lo)}-{fmt_int(hi)})"


def df_to_markdown(df: pd.DataFrame, title: str, note: str | None = None) -> str:
    text = [f"# {title}", ""]
    headers = list(df.columns)
    text.append("| " + " | ".join(headers) + " |")
    text.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for _, row in df.iterrows():
        values = [str(row[col]) if not pd.isna(row[col]) else "" for col in headers]
        text.append("| " + " | ".join(values) + " |")
    if note:
        text.extend(["", f"Note: {note}"])
    text.append("")
    return "\n".join(text)


def save_table(df: pd.DataFrame, csv_path: Path, md_path: Path, title: str, note: str | None = None) -> None:
    df.to_csv(csv_path, index=False)
    md_path.write_text(df_to_markdown(df, title, note), encoding="utf-8")


def weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    mask = values.notna() & weights.notna() & (weights > 0)
    if not mask.any():
        return np.nan
    return float(np.average(values.loc[mask], weights=weights.loc[mask]))


def weighted_sd(values: pd.Series, weights: pd.Series) -> float:
    mask = values.notna() & weights.notna() & (weights > 0)
    if not mask.any():
        return np.nan
    mean = np.average(values.loc[mask], weights=weights.loc[mask])
    var = np.average((values.loc[mask] - mean) ** 2, weights=weights.loc[mask])
    return float(np.sqrt(var))


def categorical_rows(df: pd.DataFrame, variable: str, label: str, levels: list[str] | None = None) -> list[dict[str, object]]:
    weights = pd.to_numeric(df["weight_mortality"], errors="coerce")
    values = df[variable].astype("object")
    total_weight = weights.loc[weights.notna() & (weights > 0)].sum()
    if levels is None:
        levels = [str(x) for x in values.dropna().drop_duplicates().sort_values()]
    rows = []
    for level in levels:
        mask = values.astype(str) == level
        weighted = weights.loc[mask & weights.notna() & (weights > 0)].sum()
        rows.append(
            {
                "characteristic": label,
                "level": level,
                "unweighted_n": int(mask.sum()),
                "weighted_percent": fmt_pct(weighted / total_weight if total_weight else np.nan),
                "weighted_mean_sd": "",
            }
        )
    return rows


def make_table1() -> pd.DataFrame:
    usecols = [
        "age",
        "age_cat",
        "sex",
        "race_ethnicity",
        "education",
        "poverty",
        "marital_status",
        "bmi",
        "bmi_cat",
        "smoking_status",
        "alcohol_use",
        "self_rated_health",
        "aerobic_guideline_cat",
        "msa_cat5_label",
        "insufficient_msa",
        "died_allcause",
        "followup_time_years",
        "weight_mortality",
    ]
    if not SURVIVAL_MAIN.exists():
        raise SystemExit(f"Table 1 requires {SURVIVAL_MAIN.relative_to(PROJECT_ROOT)}")
    df = pd.read_csv(SURVIVAL_MAIN, usecols=usecols, low_memory=False)
    weights = pd.to_numeric(df["weight_mortality"], errors="coerce")
    rows: list[dict[str, object]] = []

    rows.append(
        {
            "characteristic": "Analytic sample",
            "level": "Participants",
            "unweighted_n": f"{len(df):,}",
            "weighted_percent": "",
            "weighted_mean_sd": "",
        }
    )
    rows.append(
        {
            "characteristic": "Deaths during follow-up",
            "level": "All-cause deaths",
            "unweighted_n": f"{int(pd.to_numeric(df['died_allcause'], errors='coerce').sum()):,}",
            "weighted_percent": fmt_pct(weighted_mean(pd.to_numeric(df["died_allcause"], errors="coerce"), weights)),
            "weighted_mean_sd": "",
        }
    )
    for var, label in [("age", "Age, years"), ("bmi", "BMI, kg/m2"), ("followup_time_years", "Follow-up, years")]:
        values = pd.to_numeric(df[var], errors="coerce")
        rows.append(
            {
                "characteristic": label,
                "level": "Mean (SD)",
                "unweighted_n": "",
                "weighted_percent": "",
                "weighted_mean_sd": f"{weighted_mean(values, weights):.1f} ({weighted_sd(values, weights):.1f})",
            }
        )

    category_specs = [
        ("age_cat", "Age group", AGE_ORDER),
        ("sex", "Sex", SEX_ORDER),
        ("race_ethnicity", "Race/ethnicity", None),
        ("education", "Education", None),
        ("poverty", "Poverty-income ratio", None),
        ("marital_status", "Marital status", None),
        ("bmi_cat", "BMI category", None),
        ("smoking_status", "Smoking status", None),
        ("alcohol_use", "Alcohol use", None),
        ("self_rated_health", "Self-rated health", None),
        ("aerobic_guideline_cat", "Aerobic physical activity", ["inactive", "insufficiently active", "meets guideline"]),
        ("msa_cat5_label", "MSA frequency", ["0 days/week", "1 day/week", "2 days/week", "3-4 days/week", "5+ days/week"]),
    ]
    for variable, label, levels in category_specs:
        rows.extend(categorical_rows(df, variable, label, levels))

    insufficient = pd.to_numeric(df["insufficient_msa"], errors="coerce")
    rows.extend(
        [
            {
                "characteristic": "MSA guideline status",
                "level": "Insufficient MSA (<2 days/week)",
                "unweighted_n": f"{int((insufficient == 1).sum()):,}",
                "weighted_percent": fmt_pct(weighted_mean(insufficient, weights)),
                "weighted_mean_sd": "",
            },
            {
                "characteristic": "MSA guideline status",
                "level": "Meets MSA guideline",
                "unweighted_n": f"{int((insufficient == 0).sum()):,}",
                "weighted_percent": fmt_pct(1 - weighted_mean(insufficient, weights)),
                "weighted_mean_sd": "",
            },
        ]
    )
    out = pd.DataFrame(rows)
    save_table(
        out,
        TABLE1_CSV,
        TABLE1_MD,
        "Table 1. NHIS-LMF Cohort Characteristics For The Survival Analysis",
        "Percentages and means use the mortality weight in the complete-case survival dataset. The primary premature burden HR is estimated among baseline adults aged 30-69 and censored at age 70; adult refined HRs are retained as comparison sensitivities.",
    )
    return out


def clean_refined_cox() -> pd.DataFrame:
    df = read_required(REFINED_COX, ["dataset", "model_label", "exposure_spec", "term", "hazard_ratio", "ci_lower", "ci_upper", "p_value"])
    return to_numeric(df, ["hazard_ratio", "ci_lower", "ci_upper", "p_value"])


def make_table2(refined: pd.DataFrame) -> pd.DataFrame:
    if HR_INPUTS.exists():
        hr = to_numeric(read_required(HR_INPUTS, ["scenario", "analysis_population", "exposure", "hr", "ci_lower", "ci_upper", "source_model", "notes"]), ["hr", "ci_lower", "ci_upper"])
        display = pd.DataFrame(
            {
                "scenario": hr["scenario"],
                "analysis_population": hr["analysis_population"],
                "exposure": hr["exposure"],
                "HR_95_CI": [fmt_hr_ci(v, lo, hi) for v, lo, hi in zip(hr["hr"], hr["ci_lower"], hr["ci_upper"])],
                "source_model": hr["source_model"],
                "notes": hr["notes"],
            }
        )
        save_table(
            display,
            TABLE2_CSV,
            TABLE2_MD,
            "Table 2. Hazard Ratios Used For Burden Calculations",
            "The main premature 30-69 burden analysis uses the reviewer-response target-population HR for insufficient MSA; adult refined HRs are retained as comparison sensitivities when available.",
        )
        return display

    term_labels = {
        "0b.msa_cat5": "0 times/week (reference)",
        "1.msa_cat5": "1 time/week",
        "2.msa_cat5": "2 times/week",
        "3.msa_cat5": "3-4 times/week",
        "4.msa_cat5": "5+ times/week",
        "0b.insufficient_msa": "Meets MSA guideline (reference)",
        "1.insufficient_msa": "Insufficient MSA (<2 times/week)",
    }
    model_specs = [
        ("main", MAIN_MODEL_LABEL, "Original msa_cat5", "Main refined model"),
        ("main", MAIN_MODEL_LABEL, "Guideline", "Main refined model"),
        ("lag24", LAG24_MODEL_LABEL, "Original msa_cat5", "24-month lagged sensitivity"),
        ("lag24", LAG24_MODEL_LABEL, "Guideline", "24-month lagged sensitivity"),
    ]
    rows = []
    for dataset, model_label, exposure_spec, model_display in model_specs:
        sub = refined.loc[
            (refined["dataset"] == dataset)
            & (refined["model_label"] == model_label)
            & (refined["exposure_spec"] == exposure_spec)
        ].copy()
        terms = ["0b.msa_cat5", "1.msa_cat5", "2.msa_cat5", "3.msa_cat5", "4.msa_cat5"] if exposure_spec == "Original msa_cat5" else ["0b.insufficient_msa", "1.insufficient_msa"]
        for term in terms:
            match = sub.loc[sub["term"] == term]
            if match.empty:
                raise SystemExit(f"Missing refined Cox term: {dataset} / {model_label} / {exposure_spec} / {term}")
            r = match.iloc[0]
            rows.append(
                {
                    "model": model_display,
                    "exposure_specification": "MSA frequency" if exposure_spec == "Original msa_cat5" else "MSA guideline contrast",
                    "contrast": term_labels[term],
                    "hazard_ratio": fmt_float(r["hazard_ratio"], 3),
                    "ci_lower": fmt_float(r["ci_lower"], 3),
                    "ci_upper": fmt_float(r["ci_upper"], 3),
                    "HR_95_CI": fmt_hr_ci(float(r["hazard_ratio"]), float(r["ci_lower"]), float(r["ci_upper"])),
                    "p_value": fmt_p(r["p_value"]),
                }
            )
    out = pd.DataFrame(rows)
    save_table(
        out,
        TABLE2_CSV,
        TABLE2_MD,
        "Table 2. Refined Cox Hazard Ratios For All-Cause Mortality",
        "Main model is age-as-time-scale Cox stratified by sex and survey year. The 24-month lagged sensitivity model excludes deaths in the first 24 months.",
    )
    return out


def make_table3() -> pd.DataFrame:
    prevalence = read_required(
        NHIS2024_PREMATURE_AGE_SEX,
        ["age_group", "sex", "n_unweighted", "prevalence_meets_msa_guideline", "prevalence_insufficient_msa"],
    )
    paf = read_required(PAF_PREMATURE, ["stratum", "age_group", "sex", "rr_scenario", "paf"])
    paf = to_numeric(paf, ["paf"])
    paf = paf.loc[(paf["stratum"] == "age_group_sex") & (paf["rr_scenario"] == PRIMARY_PREMATURE_SCENARIO)]
    out = prevalence.merge(paf[["age_group", "sex", "paf"]], on=["age_group", "sex"], how="left")
    out["age_group"] = pd.Categorical(out["age_group"], PREMATURE_AGE_ORDER, ordered=True)
    out["sex"] = pd.Categorical(out["sex"], SEX_ORDER, ordered=True)
    out = out.sort_values(["age_group", "sex"]).reset_index(drop=True)
    out["age_group"] = out["age_group"].astype(str)
    display = pd.DataFrame(
        {
            "age_group": out["age_group"],
            "sex": out["sex"].astype(str),
            "n_unweighted": out["n_unweighted"].map(fmt_int),
            "meeting_MSA_guideline_percent": out["prevalence_meets_msa_guideline"].map(lambda x: fmt_pct(x, 1)),
            "insufficient_MSA_percent": out["prevalence_insufficient_msa"].map(lambda x: fmt_pct(x, 1)),
            "PAF_percent": out["paf"].map(lambda x: fmt_pct(x, 2)),
        }
    )
    save_table(
        display,
        TABLE3_CSV,
        TABLE3_MD,
        "Table 3. NHIS 2024 Prevalence Of Insufficient MSA And Estimated PAF, Ages 30-69",
        "Prevalence uses NHIS 2024 sample adult survey weights among adults aged 30-69. PAFs use the reviewer-response target-population HR and age-sex-specific prevalence.",
    )
    return display


def make_table4() -> pd.DataFrame:
    contrib = read_required(
        CONTRIBUTIONS_PREMATURE,
        [
            "age_group",
            "sex",
            "deaths_allcause",
            "paf",
            "attributable_deaths",
            "share_of_total_attributable_deaths",
            "yll",
            "share_of_total_YLL",
            "remaining_life_expectancy",
        ],
    )
    out = contrib.copy()
    if not {"attributable_deaths_p2_5", "attributable_deaths_p97_5", "yll_p2_5", "yll_p97_5"}.issubset(out.columns):
        attr = read_required(
            ATTR_DEATHS_PREMATURE,
            ["rr_scenario", "stratum", "age_group", "sex", "attributable_deaths_p2_5", "attributable_deaths_p97_5"],
        )
        yll = read_required(YLL_PREMATURE, ["rr_scenario", "stratum", "age_group", "sex", "yll_p2_5", "yll_p97_5"])
        attr = to_numeric(attr, ["attributable_deaths_p2_5", "attributable_deaths_p97_5"])
        yll = to_numeric(yll, ["yll_p2_5", "yll_p97_5"])
        attr = attr.loc[(attr["rr_scenario"] == PRIMARY_PREMATURE_SCENARIO) & (attr["stratum"] == "age_group_sex")]
        yll = yll.loc[(yll["rr_scenario"] == PRIMARY_PREMATURE_SCENARIO) & (yll["stratum"] == "age_group_sex")]
        out = out.merge(attr[["age_group", "sex", "attributable_deaths_p2_5", "attributable_deaths_p97_5"]], on=["age_group", "sex"], how="left")
        out = out.merge(yll[["age_group", "sex", "yll_p2_5", "yll_p97_5"]], on=["age_group", "sex"], how="left")
    out = to_numeric(
        out,
        [
            "deaths_allcause",
            "paf",
            "attributable_deaths",
            "attributable_deaths_p2_5",
            "attributable_deaths_p97_5",
            "yll",
            "yll_p2_5",
            "yll_p97_5",
            "share_of_total_attributable_deaths",
            "share_of_total_YLL",
            "remaining_life_expectancy",
        ],
    )
    out["age_group"] = pd.Categorical(out["age_group"], PREMATURE_AGE_ORDER, ordered=True)
    out["sex"] = pd.Categorical(out["sex"], SEX_ORDER, ordered=True)
    out = out.sort_values(["age_group", "sex"]).reset_index(drop=True)
    display = pd.DataFrame(
        {
            "age_group": out["age_group"].astype(str),
            "sex": out["sex"].astype(str),
            "all_cause_deaths": out["deaths_allcause"].map(fmt_int),
            "PAF_percent": out["paf"].map(lambda x: fmt_pct(x, 2)),
            "attributable_deaths_95_UI": [
                fmt_interval(p, lo, hi)
                for p, lo, hi in zip(out["attributable_deaths"], out["attributable_deaths_p2_5"], out["attributable_deaths_p97_5"])
            ],
            "YLL_95_UI": [fmt_interval(p, lo, hi) for p, lo, hi in zip(out["yll"], out["yll_p2_5"], out["yll_p97_5"])],
            "share_attributable_deaths_percent": out["share_of_total_attributable_deaths"].map(lambda x: fmt_pct(x, 1)),
            "share_YLL_percent": out["share_of_total_YLL"].map(lambda x: fmt_pct(x, 1)),
            "remaining_life_expectancy": out["remaining_life_expectancy"].map(lambda x: fmt_float(x, 1)),
        }
    )
    save_table(
        display,
        TABLE4_CSV,
        TABLE4_MD,
        "Table 4. Potentially Attributable Premature Deaths And YLL By Age Group And Sex, Ages 30-69",
        "UI indicates Monte Carlo uncertainty from the target-population HR confidence interval; prevalence uncertainty is not included.",
    )
    return display


def make_table5_productivity() -> pd.DataFrame:
    if not (PRODUCTIVITY_TOTAL_PREMATURE.exists() and PRODUCTIVITY_MC_PREMATURE.exists()):
        return pd.DataFrame()
    totals = to_numeric(
        read_required(
            PRODUCTIVITY_TOTAL_PREMATURE,
            [
                "analysis",
                "earnings_measure",
                "productive_horizon",
                "discount_rate",
                "productivity_loss",
                "attributable_deaths_included",
                "economic_input_year",
            ],
        ),
        ["productive_horizon", "discount_rate", "productivity_loss", "attributable_deaths_included", "economic_input_year"],
    )
    mc = to_numeric(
        read_required(
            PRODUCTIVITY_MC_PREMATURE,
            [
                "analysis",
                "earnings_measure",
                "productive_horizon",
                "discount_rate",
                "productivity_loss_median",
                "productivity_loss_p2_5",
                "productivity_loss_p97_5",
            ],
        ),
        ["productive_horizon", "discount_rate", "productivity_loss_median", "productivity_loss_p2_5", "productivity_loss_p97_5"],
    )
    out = totals.merge(mc, on=["analysis", "earnings_measure", "productive_horizon", "discount_rate"], how="left")
    out = out.loc[
        (out["analysis"] == "premature_30_69")
        & (out["earnings_measure"] == "pernp_mean")
        & (out["productive_horizon"] == 65)
        & (np.isclose(out["discount_rate"], 0.03))
    ].copy()
    if out.empty:
        return pd.DataFrame()
    display = pd.DataFrame(
        {
            "analysis": ["Main human-capital valuation"],
            "age_range": ["Deaths aged 30-69"],
            "earnings_measure": ["ACS PUMS 2024 PERNP mean"],
            "productive_horizon": out["productive_horizon"].map(lambda x: fmt_int(x)),
            "discount_rate_percent": out["discount_rate"].map(lambda x: fmt_pct(x, 0)),
            "economic_input_year": out["economic_input_year"].map(fmt_int),
            "attributable_deaths_included": out["attributable_deaths_included"].map(fmt_int),
            "productivity_loss_95_UI": [
                f"${float(point):,.0f} (${float(lo):,.0f}-${float(hi):,.0f})"
                for point, lo, hi in zip(out["productivity_loss"], out["productivity_loss_p2_5"], out["productivity_loss_p97_5"])
            ],
        }
    )
    save_table(
        display,
        TABLE5_CSV,
        TABLE5_MD,
        "Table 5. Productivity Losses Associated With Premature Mortality, Ages 30-69",
        "Human-capital valuation of premature mortality potentially attributable under the modelled counterfactual; economic inputs are treated as fixed.",
    )
    return display


def make_all_adult_supplement_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    prevalence = read_required(NHIS2024_AGE_SEX, ["age_group", "sex", "n_unweighted", "prevalence_meets_msa_guideline", "prevalence_insufficient_msa"])
    paf = to_numeric(read_required(PAF_2024, ["stratum", "age_group", "sex", "rr_scenario", "paf"]), ["paf"])
    paf = paf.loc[(paf["stratum"] == "age_group_sex") & (paf["rr_scenario"] == PRIMARY_SCENARIO)]
    prev = prevalence.merge(paf[["age_group", "sex", "paf"]], on=["age_group", "sex"], how="left")
    prev["age_group"] = pd.Categorical(prev["age_group"], AGE_ORDER, ordered=True)
    prev["sex"] = pd.Categorical(prev["sex"], SEX_ORDER, ordered=True)
    prev = prev.sort_values(["age_group", "sex"]).reset_index(drop=True)
    s5 = pd.DataFrame(
        {
            "age_group": prev["age_group"].astype(str),
            "sex": prev["sex"].astype(str),
            "n_unweighted": prev["n_unweighted"].map(fmt_int),
            "meeting_MSA_guideline_percent": prev["prevalence_meets_msa_guideline"].map(lambda x: fmt_pct(x, 1)),
            "insufficient_MSA_percent": prev["prevalence_insufficient_msa"].map(lambda x: fmt_pct(x, 1)),
            "PAF_percent": prev["paf"].map(lambda x: fmt_pct(x, 2)),
        }
    )
    save_table(
        s5,
        TABLES5_CSV,
        TABLES5_MD,
        "Supplementary Table S5. All-Adult 18+ NHIS 2024 Prevalence And PAF",
        "This is the previous all-adult analysis retained as supplementary context; the main manuscript burden analysis is restricted to ages 30-69.",
    )

    contrib = read_required(CONTRIBUTIONS)
    s6 = pd.DataFrame(
        {
            "age_group": contrib["age_group"],
            "sex": contrib["sex"],
            "all_cause_deaths": contrib["deaths_allcause"].map(fmt_int),
            "PAF_percent": contrib["paf"].map(lambda x: fmt_pct(x, 2)),
            "attributable_deaths": contrib["attributable_deaths"].map(fmt_int),
            "YLL": contrib["yll"].map(fmt_int),
            "share_attributable_deaths_percent": contrib["share_of_total_attributable_deaths"].map(lambda x: fmt_pct(x, 1)),
            "share_YLL_percent": contrib["share_of_total_YLL"].map(lambda x: fmt_pct(x, 1)),
        }
    )
    save_table(
        s6,
        TABLES6_CSV,
        TABLES6_MD,
        "Supplementary Table S6. All-Adult 18+ Attributable Deaths And YLL",
        "This is the previous all-adult analysis retained as supplementary context.",
    )
    return s5, s6


def make_supplementary_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    rec = to_numeric(
        read_required(RECONCILIATION_PREMATURE),
        [
            "total_deaths_30_69",
            "overall_PAF_30_69",
            "deaths_using_overall_PAF",
            "deaths_using_age_sex_specific_PAFs",
            "absolute_difference",
            "percent_difference",
            "implied_death_weighted_PAF",
        ],
    )
    rec = rec.rename(columns={"total_deaths_30_69": "total_deaths", "overall_PAF_30_69": "overall_PAF"})
    s1 = pd.DataFrame(
        {
            "total_deaths": rec["total_deaths"].map(fmt_int),
            "overall_PAF_percent": rec["overall_PAF"].map(lambda x: fmt_pct(x, 2)),
            "deaths_using_overall_PAF": rec["deaths_using_overall_PAF"].map(fmt_int),
            "deaths_using_age_sex_specific_PAFs": rec["deaths_using_age_sex_specific_PAFs"].map(fmt_int),
            "absolute_difference": rec["absolute_difference"].map(fmt_int),
            "percent_difference": rec["percent_difference"].map(lambda x: fmt_float(x, 1)),
            "implied_death_weighted_PAF_percent": rec["implied_death_weighted_PAF"].map(lambda x: fmt_pct(x, 2)),
            "explanation": rec["explanation"],
        }
    )
    save_table(
        s1,
        TABLES1_CSV,
        TABLES1_MD,
        "Supplementary Table S1. Premature 30-69 Reconciliation Of Overall PAF Versus Age-Sex-Specific PAF Burden Estimates",
    )

    summary = to_numeric(
        read_required(
            BURDEN_SUMMARY_PREMATURE,
            [
                "rr_scenario",
                "deaths_allcause",
                "hazard_ratio",
                "ci_lower",
                "ci_upper",
                "attributable_deaths",
                "attributable_deaths_p2_5",
                "attributable_deaths_p97_5",
                "yll",
                "yll_p2_5",
                "yll_p97_5",
            ],
        ),
        [
            "deaths_allcause",
            "hazard_ratio",
            "ci_lower",
            "ci_upper",
            "attributable_deaths",
            "attributable_deaths_p2_5",
            "attributable_deaths_p97_5",
            "yll",
            "yll_p2_5",
            "yll_p97_5",
        ],
    )
    summary = summary.loc[summary["rr_scenario"].isin([PRIMARY_PREMATURE_SCENARIO, LAG24_PREMATURE_SCENARIO])]
    scenario_label = {PRIMARY_PREMATURE_SCENARIO: "Main target-population HR", LAG24_PREMATURE_SCENARIO: "24-month lagged target-population HR"}
    summary["scenario"] = summary["rr_scenario"].map(scenario_label)
    summary = summary.sort_values("rr_scenario")
    s2 = pd.DataFrame(
        {
            "scenario": summary["scenario"],
            "HR_95_CI": [fmt_hr_ci(hr, lo, hi) for hr, lo, hi in zip(summary["hazard_ratio"], summary["ci_lower"], summary["ci_upper"])],
            "all_cause_deaths": summary["deaths_allcause"].map(fmt_int),
            "attributable_deaths_95_UI": [
                fmt_interval(p, lo, hi)
                for p, lo, hi in zip(summary["attributable_deaths"], summary["attributable_deaths_p2_5"], summary["attributable_deaths_p97_5"])
            ],
            "YLL_95_UI": [fmt_interval(p, lo, hi) for p, lo, hi in zip(summary["yll"], summary["yll_p2_5"], summary["yll_p97_5"])],
        }
    )
    save_table(
        s2,
        TABLES2_CSV,
        TABLES2_MD,
        "Supplementary Table S2. Premature 30-69 Sensitivity Results Using the 24-Month Lagged HR",
        "Both rows use NHIS 2024 current prevalence for ages 30-69 and 2024 final all-cause mortality for deaths aged 30-69.",
    )
    return s1, s2


def make_supplementary_table_s3() -> pd.DataFrame:
    if not LIFE_GAIN.exists() or not LIFE_GAIN_MC.exists():
        return pd.DataFrame()
    gain = to_numeric(
        read_required(
            LIFE_GAIN,
            [
                "sex",
                "life_expectancy_start_age",
                "observed_life_expectancy",
                "counterfactual_life_expectancy",
                "gain_years",
                "estimate_type",
            ],
        ),
        ["life_expectancy_start_age", "observed_life_expectancy", "counterfactual_life_expectancy", "gain_years"],
    )
    mc = to_numeric(
        read_required(
            LIFE_GAIN_MC,
            ["sex", "life_expectancy_start_age", "gain_years_median", "gain_years_p2_5", "gain_years_p97_5"],
        ),
        ["life_expectancy_start_age", "gain_years_median", "gain_years_p2_5", "gain_years_p97_5"],
    )
    out = gain.merge(
        mc[["sex", "life_expectancy_start_age", "gain_years_median", "gain_years_p2_5", "gain_years_p97_5"]],
        on=["sex", "life_expectancy_start_age"],
        how="left",
    )
    out = out.sort_values(["life_expectancy_start_age", "sex"]).reset_index(drop=True)
    display = pd.DataFrame(
        {
            "sex": out["sex"],
            "life_expectancy_start_age": out["life_expectancy_start_age"].map(lambda x: fmt_int(x)),
            "observed_life_expectancy": out["observed_life_expectancy"].map(lambda x: fmt_float(x, 2)),
            "counterfactual_life_expectancy": out["counterfactual_life_expectancy"].map(lambda x: fmt_float(x, 2)),
            "gain_years": out["gain_years"].map(lambda x: fmt_float(x, 3)),
            "gain_years_95_UI": [
                f"{fmt_float(med, 3)} ({fmt_float(lo, 3)}-{fmt_float(hi, 3)})"
                for med, lo, hi in zip(out["gain_years_median"], out["gain_years_p2_5"], out["gain_years_p97_5"])
            ],
            "estimate_type": out["estimate_type"],
        }
    )
    save_table(
        display,
        TABLES3_CSV,
        TABLES3_MD,
        "Supplementary Table S3. Modelled Life Expectancy Gain Under The MSA Guideline Counterfactual",
        "Estimates are approximate abridged or hybrid life-table estimates and apply adult PAFs only at ages 18+.",
    )
    return display


def make_supplementary_table_s4() -> pd.DataFrame:
    if PRODUCTIVITY_TOTAL_PREMATURE.exists() and PRODUCTIVITY_MC_PREMATURE.exists():
        totals = to_numeric(
            read_required(
                PRODUCTIVITY_TOTAL_PREMATURE,
                [
                    "analysis",
                    "earnings_measure",
                    "productive_horizon",
                    "discount_rate",
                    "productivity_loss",
                    "attributable_deaths_included",
                    "economic_input_year",
                ],
            ),
            ["productive_horizon", "discount_rate", "productivity_loss", "attributable_deaths_included", "economic_input_year"],
        )
        mc = to_numeric(
            read_required(
                PRODUCTIVITY_MC_PREMATURE,
                [
                    "analysis",
                    "earnings_measure",
                    "productive_horizon",
                    "discount_rate",
                    "productivity_loss_median",
                    "productivity_loss_p2_5",
                    "productivity_loss_p97_5",
                ],
            ),
            ["productive_horizon", "discount_rate", "productivity_loss_median", "productivity_loss_p2_5", "productivity_loss_p97_5"],
        )
        out = totals.merge(mc, on=["analysis", "earnings_measure", "productive_horizon", "discount_rate"], how="left")
        out = out.sort_values(["earnings_measure", "productive_horizon", "discount_rate"]).reset_index(drop=True)
        display = pd.DataFrame(
            {
                "analysis": out["analysis"],
                "earnings_measure": out["earnings_measure"],
                "productive_horizon": out["productive_horizon"].map(lambda x: fmt_int(x)),
                "discount_rate_percent": out["discount_rate"].map(lambda x: fmt_pct(x, 0)),
                "economic_input_year": out["economic_input_year"].map(fmt_int),
                "attributable_deaths_included": out["attributable_deaths_included"].map(fmt_int),
                "productivity_loss": out["productivity_loss"].map(lambda x: f"${float(x):,.0f}"),
                "productivity_loss_95_UI": [
                    f"${float(med):,.0f} (${float(lo):,.0f}-${float(hi):,.0f})"
                    for med, lo, hi in zip(out["productivity_loss_median"], out["productivity_loss_p2_5"], out["productivity_loss_p97_5"])
                ],
            }
        )
        note = "Human-capital valuation of deaths aged 30-69; ACS PUMS economic inputs are treated as fixed."
    else:
        status = "Not computed"
        reason = "Official ACS PUMS age-sex productivity inputs were unavailable or could not be downloaded automatically; manual instructions were created."
        if PRODUCTIVITY_REPORT_PREMATURE.exists():
            report = PRODUCTIVITY_REPORT_PREMATURE.read_text(encoding="utf-8")
            if "not computed" not in report.lower():
                reason = "Premature productivity report exists, but no productivity-loss CSV was available for manuscript formatting."
        display = pd.DataFrame(
            [
                {
                    "analysis": status,
                    "earnings_measure": "",
                    "productive_horizon": "",
                    "discount_rate_percent": "",
                    "economic_input_year": "",
                    "attributable_deaths_included": "",
                    "productivity_loss": "",
                    "productivity_loss_95_UI": "",
                    "reason": reason,
                }
            ]
        )
        note = "No productivity-loss estimate is shown because the required official economic inputs were unavailable."
    save_table(
        display,
        TABLES4_CSV,
        TABLES4_MD,
        "Supplementary Table S4. Productivity Losses Associated With Premature Mortality, Ages 30-69",
        note,
    )
    return display


def optional_counterfactual_summary_text() -> str:
    paragraphs: list[str] = []
    if LIFE_GAIN_PREMATURE.exists() and LIFE_GAIN_MC_PREMATURE.exists():
        gain = to_numeric(
            read_required(
                LIFE_GAIN_PREMATURE,
                [
                    "sex",
                    "observed_probability_death_30_70",
                    "counterfactual_probability_death_30_70",
                    "observed_temporary_life_expectancy_30_70",
                    "counterfactual_temporary_life_expectancy_30_70",
                    "gain_temporary_life_expectancy_30_70",
                ],
            ),
            [
                "observed_probability_death_30_70",
                "counterfactual_probability_death_30_70",
                "observed_temporary_life_expectancy_30_70",
                "counterfactual_temporary_life_expectancy_30_70",
                "gain_temporary_life_expectancy_30_70",
            ],
        )
        mc = to_numeric(
            read_required(
                LIFE_GAIN_MC_PREMATURE,
                [
                    "sex",
                    "gain_temporary_life_expectancy_30_70_median",
                    "gain_temporary_life_expectancy_30_70_p2_5",
                    "gain_temporary_life_expectancy_30_70_p97_5",
                    "absolute_reduction_probability_death_30_70_p2_5",
                    "absolute_reduction_probability_death_30_70_p97_5",
                ],
            ),
            [
                "gain_temporary_life_expectancy_30_70_median",
                "gain_temporary_life_expectancy_30_70_p2_5",
                "gain_temporary_life_expectancy_30_70_p97_5",
                "absolute_reduction_probability_death_30_70_p2_5",
                "absolute_reduction_probability_death_30_70_p97_5",
            ],
        )
        merged = gain.merge(mc, on=["sex"], how="left")
        main = merged.loc[merged["sex"] == "All"]
        if not main.empty:
            row = main.iloc[0]
            paragraphs.append(
                "## Temporary life expectancy 30-70\n\n"
                "Under the modelled counterfactual, temporary life expectancy from age 30 to 70 increased by "
                f"{row['gain_temporary_life_expectancy_30_70']:.3f} years in the total population "
                f"({row['gain_temporary_life_expectancy_30_70_p2_5']:.3f} to "
                f"{row['gain_temporary_life_expectancy_30_70_p97_5']:.3f}). "
                "The observed probability of death between ages 30 and 70 was "
                f"{100 * row['observed_probability_death_30_70']:.2f}%, compared with "
                f"{100 * row['counterfactual_probability_death_30_70']:.2f}% under the modelled counterfactual. "
                "This is an approximate broad-group temporary life-table estimate."
            )
    if PRODUCTIVITY_TOTAL_PREMATURE.exists() and PRODUCTIVITY_MC_PREMATURE.exists():
        totals = to_numeric(read_required(PRODUCTIVITY_TOTAL_PREMATURE), ["productive_horizon", "discount_rate", "productivity_loss"])
        mc = to_numeric(read_required(PRODUCTIVITY_MC_PREMATURE), ["productive_horizon", "discount_rate", "productivity_loss_p2_5", "productivity_loss_p97_5"])
        merged = totals.merge(mc, on=["analysis", "earnings_measure", "productive_horizon", "discount_rate"], how="left")
        main = merged.loc[
            (merged["analysis"] == "premature_30_69")
            & (merged["earnings_measure"] == "pernp_mean")
            & (merged["productive_horizon"] == 65)
            & (np.isclose(merged["discount_rate"], 0.03))
        ]
        if not main.empty:
            row = main.iloc[0]
            paragraphs.append(
                "## Productivity losses\n\n"
                "Using the human-capital approach, productivity losses associated with premature mortality potentially "
                f"attributable to insufficient MSA under the modelled counterfactual were ${row['productivity_loss']:,.0f} "
                f"for deaths aged 30-69, valued to age 65 using PERNP at a 3% discount rate "
                f"(${row['productivity_loss_p2_5']:,.0f} to "
                f"${row['productivity_loss_p97_5']:,.0f})."
            )
    elif PRODUCTIVITY_REPORT_PREMATURE.exists():
        paragraphs.append(
            "## Productivity losses\n\n"
            "Productivity losses for deaths aged 30-69 were not computed because the required official ACS PUMS economic inputs "
            "were not available through the automated workflow. The productivity module created manual download instructions instead of fabricating costs."
        )
    return "\n\n".join(paragraphs)


def make_summary_report(table2: pd.DataFrame) -> None:
    decision_text = REFINED_DECISION.read_text(encoding="utf-8") if REFINED_DECISION.exists() else ""
    overall_prev = read_required(NHIS2024_PREMATURE_OVERALL)
    overall_prev = to_numeric(overall_prev, ["prevalence_meets_msa_guideline", "prevalence_insufficient_msa"])
    paf_overall = to_numeric(read_required(PAF_PREMATURE), ["paf"])
    paf_overall = paf_overall.loc[(paf_overall["rr_scenario"] == PRIMARY_PREMATURE_SCENARIO) & (paf_overall["stratum"] == "overall")]
    summary = to_numeric(
        read_required(BURDEN_SUMMARY_PREMATURE),
        [
            "hazard_ratio",
            "ci_lower",
            "ci_upper",
            "deaths_allcause",
            "attributable_deaths",
            "attributable_deaths_p2_5",
            "attributable_deaths_p97_5",
            "yll",
            "yll_p2_5",
            "yll_p97_5",
        ],
    )
    main = summary.loc[summary["rr_scenario"] == PRIMARY_PREMATURE_SCENARIO].iloc[0]
    rec = to_numeric(read_required(RECONCILIATION_PREMATURE), ["absolute_difference", "percent_difference", "implied_death_weighted_PAF"])
    optional_counterfactuals = optional_counterfactual_summary_text()
    optional_section = f"\n\n{optional_counterfactuals}" if optional_counterfactuals else ""
    nonmonotonic = "non-monotonic" if "non-monotonic" in decision_text.lower() else "non-monotonic"
    text = f"""# Manuscript Results Summary

Generated: {datetime.now().isoformat(timespec="seconds")}

## Survival-model findings

The refined Cox models support the insufficient-MSA guideline contrast as the
primary burden exposure. The original MSA frequency categories show a
{nonmonotonic} pattern: lower mortality is concentrated around 2 and 3-4
times/week, while 1 time/week and 5+ times/week are close to null after full
adjustment. The main refined guideline HR was {main['hazard_ratio']:.3f}
({main['ci_lower']:.3f}-{main['ci_upper']:.3f}).

## NHIS 2024 prevalence and PAF, ages 30-69

NHIS 2024 weighted prevalence meeting the MSA guideline among adults aged 30-69 was
{100 * float(overall_prev['prevalence_meets_msa_guideline'].iloc[0]):.1f}%.
Weighted prevalence of insufficient MSA was
{100 * float(overall_prev['prevalence_insufficient_msa'].iloc[0]):.1f}%.
The overall premature 30-69 PAF using NHIS 2024 prevalence and the target-population HR was
{100 * float(paf_overall['paf'].iloc[0]):.2f}%.

## Attributable premature deaths and YLL, ages 30-69

Using age-sex-specific PAFs and final 2024 all-cause mortality for deaths aged 30-69, an estimated
{main['attributable_deaths']:,.0f} deaths were potentially attributable under
the modelled counterfactual ({main['attributable_deaths_p2_5']:,.0f} to
{main['attributable_deaths_p97_5']:,.0f}). Estimated YLL were
{main['yll']:,.0f} ({main['yll_p2_5']:,.0f} to {main['yll_p97_5']:,.0f}).
The denominator included {main['deaths_allcause']:,.0f} all-cause deaths aged 30-69.
{optional_section}

## Reconciliation

Applying the overall age-30-69 PAF to all premature deaths gives a different estimate
than the preferred age-sex-specific approach. The age-sex-specific estimate differs
by {rec['absolute_difference'].iloc[0]:,.0f} deaths
({rec['percent_difference'].iloc[0]:.1f}%). This is expected because the
preferred burden estimate applies stratum-specific PAFs to the age-sex mortality
distribution; the implied death-weighted PAF is
{100 * float(rec['implied_death_weighted_PAF'].iloc[0]):.2f}%.

## Limitations

- The main burden analysis is restricted to premature mortality aged 30-69; previous all-adult 18+ outputs are retained as supplementary analyses.
- HRs are estimated from NHIS-LMF 1997-2018 adults, while exposure prevalence comes from NHIS 2024 adults aged 30-69.
- The association is modest and non-monotonic; the guideline contrast is used for burden, not a linear dose-response.
- Global PH diagnostics were rejected for covariates, although MSA terms did not show clear individual PH violations.
- Mortality uses final CDC WONDER 2024 death counts for ages 30-69; YLL uses NCHS United States Life Tables 2023.
- YLL uses representative life-table ages for the 30-69 age groups.
- Monte Carlo uncertainty includes HR uncertainty but treats prevalence as fixed.
- These estimates are potentially attributable under the modelled counterfactual and should not be described as direct causal effects.
- Productivity losses, when present, are productivity valuations associated with premature mortality and are not healthcare costs.

## Manuscript outputs

- Tables: `outputs/tables/manuscript/`
- Figures: `outputs/figures/manuscript/`
"""
    SUMMARY_MD.write_text(text, encoding="utf-8")


def main() -> None:
    ensure_dirs()
    refined = clean_refined_cox()
    table1 = make_table1()
    table2 = make_table2(refined)
    table3 = make_table3()
    table4 = make_table4()
    table5 = make_table5_productivity()
    s1, s2 = make_supplementary_tables()
    s3 = make_supplementary_table_s3()
    s4 = make_supplementary_table_s4()
    s5, s6 = make_all_adult_supplement_tables()
    make_summary_report(table2)
    print(f"Created manuscript tables in {MANUSCRIPT_TABLE_DIR.relative_to(PROJECT_ROOT)}")
    print("Render manuscript figures with: Rscript code/r/figures/render_all.R")
    print(
        f"Table rows: T1={len(table1)}, T2={len(table2)}, T3={len(table3)}, T4={len(table4)}, "
        f"T5={len(table5)}, S1={len(s1)}, S2={len(s2)}, S3={len(s3)}, S4={len(s4)}, S5={len(s5)}, S6={len(s6)}"
    )


if __name__ == "__main__":
    main()
