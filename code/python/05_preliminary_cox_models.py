"""Preliminary Cox models for MSA and all-cause mortality.

This is a fallback when Stata is not available. It uses lifelines if installed
and writes preliminary hazard-ratio tables only. It does not compute burden,
life expectancy, years of life lost, or economic costs.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "data/processed"
LOG_DIR = PROJECT_ROOT / "outputs/logs"
TABLE_DIR = PROJECT_ROOT / "outputs/tables"

MAIN_DTA = PROCESSED_DIR / "msa_survival_main_completecase.dta"
LAG24_DTA = PROCESSED_DIR / "msa_survival_lag24_completecase.dta"
PY_LOG = LOG_DIR / "05_preliminary_cox_models_python.log"
ISSUES = LOG_DIR / "issues_to_resolve.md"

BASE_COLS = [
    "followup_time_years",
    "died_allcause",
    "weight_mortality",
    "msa_cat5",
    "insufficient_msa",
    "age",
    "sex",
    "year",
    "race_ethnicity",
    "education",
    "poverty",
    "marital_status",
    "smoking_status",
    "alcohol_use",
    "bmi_cat",
    "self_rated_health",
    "aerobic_category",
    "diabetes",
    "hypertension",
    "cvd_history",
    "cancer_history",
]

MODEL_SPECS = [
    ("Model 1", ["msa_cat5", "age", "sex", "year"]),
    ("Model 2", ["msa_cat5", "age", "sex", "year", "race_ethnicity", "education", "poverty", "marital_status"]),
    (
        "Model 3",
        [
            "msa_cat5",
            "age",
            "sex",
            "year",
            "race_ethnicity",
            "education",
            "poverty",
            "marital_status",
            "smoking_status",
            "alcohol_use",
            "bmi_cat",
            "self_rated_health",
        ],
    ),
    (
        "Model 4",
        [
            "msa_cat5",
            "age",
            "sex",
            "year",
            "race_ethnicity",
            "education",
            "poverty",
            "marital_status",
            "smoking_status",
            "alcohol_use",
            "bmi_cat",
            "self_rated_health",
            "aerobic_category",
        ],
    ),
    (
        "Model 5",
        [
            "msa_cat5",
            "age",
            "sex",
            "year",
            "race_ethnicity",
            "education",
            "poverty",
            "marital_status",
            "smoking_status",
            "alcohol_use",
            "bmi_cat",
            "self_rated_health",
            "aerobic_category",
            "diabetes",
            "hypertension",
            "cvd_history",
            "cancer_history",
        ],
    ),
    (
        "Guideline model",
        [
            "insufficient_msa",
            "age",
            "sex",
            "year",
            "race_ethnicity",
            "education",
            "poverty",
            "marital_status",
            "smoking_status",
            "alcohol_use",
            "bmi_cat",
            "self_rated_health",
            "aerobic_category",
            "diabetes",
            "hypertension",
            "cvd_history",
            "cancer_history",
        ],
    ),
]

CATEGORICAL_REFS = {
    "msa_cat5": 0,
    "sex": None,
    "year": None,
    "race_ethnicity": None,
    "education": None,
    "poverty": None,
    "marital_status": None,
    "smoking_status": None,
    "alcohol_use": None,
    "bmi_cat": "normal weight",
    "self_rated_health": "Excellent",
    "aerobic_category": "inactive",
}

NUMERIC_BINARY = ["insufficient_msa", "diabetes", "hypertension", "cvd_history", "cancer_history"]


def ensure_dirs() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)


def timestamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def write_log(message: str) -> None:
    ensure_dirs()
    with PY_LOG.open("a", encoding="utf-8") as handle:
        handle.write(message.rstrip() + "\n")


def write_issue_once(message: str) -> None:
    ensure_dirs()
    old = ISSUES.read_text(encoding="utf-8") if ISSUES.exists() else "# Issues to Resolve\n\n"
    if message.rstrip() in old:
        return
    with ISSUES.open("w", encoding="utf-8") as handle:
        handle.write(old.rstrip() + "\n\n")
        handle.write(f"## {timestamp()}\n\n")
        handle.write(message.rstrip() + "\n")


def require_lifelines():
    if importlib.util.find_spec("lifelines") is None:
        message = (
            "Preliminary Cox models were not estimated because neither Stata was available in PATH "
            "nor the Python fallback dependency `lifelines` was installed. Install `lifelines` or "
            "run `code/stata/02_preliminary_cox_models.do` in Stata to produce the preliminary HR tables."
        )
        write_log(f"{timestamp()} - STOP: {message}")
        write_issue_once(message)
        raise SystemExit(message)
    from lifelines import CoxPHFitter

    return CoxPHFitter


def load_dataset(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_stata(path, columns=BASE_COLS, convert_categoricals=False)
    return df


def normalize_category(series: pd.Series) -> pd.Series:
    out = series.astype("object")
    out = out.where(out.notna(), np.nan)
    return out


def add_dummies(frame: pd.DataFrame, source: pd.Series, var: str, ref: object | None) -> list[str]:
    cat = normalize_category(source)
    if ref is not None:
        cat_type = pd.Categorical(cat)
        if ref in set(cat_type.categories):
            ordered = [ref] + [level for level in cat_type.categories if level != ref]
            cat = pd.Categorical(cat, categories=ordered)
    dummies = pd.get_dummies(cat, prefix=var, drop_first=True, dtype=float)
    frame[dummies.columns] = dummies
    return list(dummies.columns)


def design_matrix(df: pd.DataFrame, variables: list[str]) -> pd.DataFrame:
    frame = df[["followup_time_years", "died_allcause", "weight_mortality"]].copy()
    terms: list[str] = []
    for var in variables:
        if var == "age":
            frame["age"] = pd.to_numeric(df[var], errors="coerce")
            terms.append("age")
        elif var in NUMERIC_BINARY:
            frame[var] = pd.to_numeric(df[var], errors="coerce")
            terms.append(var)
        elif var in CATEGORICAL_REFS:
            terms.extend(add_dummies(frame, df[var], var, CATEGORICAL_REFS[var]))
        else:
            raise ValueError(f"Unhandled model variable: {var}")
    model_df = frame[["followup_time_years", "died_allcause", "weight_mortality"] + terms]
    model_df = model_df.replace([np.inf, -np.inf], np.nan).dropna()
    return model_df


def fit_model(CoxPHFitter, df: pd.DataFrame, variables: list[str], model_name: str, dataset_name: str):
    model_df = design_matrix(df, variables)
    cph = CoxPHFitter()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        cph.fit(
            model_df,
            duration_col="followup_time_years",
            event_col="died_allcause",
            weights_col="weight_mortality",
            robust=True,
            show_progress=False,
        )
    for warning in caught:
        write_issue_once(f"Preliminary Cox model warning in {dataset_name} {model_name}: {warning.message}")
    summary = cph.summary.reset_index(names="term")
    summary["dataset"] = dataset_name
    summary["model_name"] = model_name
    summary["n_used"] = len(model_df)
    return cph, model_df, summary


def clean_summary(summary: pd.DataFrame) -> pd.DataFrame:
    out = summary.rename(
        columns={
            "exp(coef)": "hazard_ratio",
            "exp(coef) lower 95%": "ci_lower",
            "exp(coef) upper 95%": "ci_upper",
            "p": "p_value",
        }
    )
    keep = ["dataset", "model_name", "term", "hazard_ratio", "ci_lower", "ci_upper", "p_value", "n_used"]
    return out[keep]


def plot_data(results: pd.DataFrame) -> pd.DataFrame:
    mask = results["term"].str.startswith("msa_cat5_", na=False)
    out = results.loc[mask, ["term", "hazard_ratio", "ci_lower", "ci_upper", "model_name"]].copy()
    labels = {
        "msa_cat5_1": "1 day/week",
        "msa_cat5_2": "2 days/week",
        "msa_cat5_3": "3-4 days/week",
        "msa_cat5_4": "5+ days/week",
        "msa_cat5_1.0": "1 day/week",
        "msa_cat5_2.0": "2 days/week",
        "msa_cat5_3.0": "3-4 days/week",
        "msa_cat5_4.0": "5+ days/week",
    }
    out["msa_category"] = out["term"].map(labels).fillna(out["term"])
    return out[["msa_category", "hazard_ratio", "ci_lower", "ci_upper", "model_name"]]


def proportional_hazards_check(cph, model_df: pd.DataFrame, model_name: str, dataset_name: str) -> None:
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            cph.check_assumptions(model_df, p_value_threshold=0.05, show_plots=False)
    except Exception as error:  # noqa: BLE001 - diagnostics should not erase fitted models.
        write_issue_once(f"Proportional hazards diagnostic failed for {dataset_name} {model_name}: {error}")
    text = buffer.getvalue().strip()
    if text:
        write_log(f"\nPH diagnostic for {dataset_name} {model_name}\n{text}\n")


def main() -> None:
    ensure_dirs()
    PY_LOG.write_text(f"{timestamp()} - Starting preliminary Cox fallback.\n", encoding="utf-8")
    CoxPHFitter = require_lifelines()

    main_df = load_dataset(MAIN_DTA)
    lag_df = load_dataset(LAG24_DTA)
    write_log(f"Loaded main rows: {len(main_df):,}")
    write_log(f"Loaded lag24 rows: {len(lag_df):,}")

    result_frames = []
    full_model = None
    full_model_df = None
    for model_name, variables in MODEL_SPECS:
        cph, model_df, summary = fit_model(CoxPHFitter, main_df, variables, model_name, "main")
        result_frames.append(clean_summary(summary))
        if model_name == "Model 5":
            full_model = cph
            full_model_df = model_df

    if full_model is not None and full_model_df is not None:
        proportional_hazards_check(full_model, full_model_df, "Model 5", "main")

    cph_lag, model_df_lag, summary_lag = fit_model(
        CoxPHFitter,
        lag_df,
        MODEL_SPECS[4][1],
        "Model 5 lag24",
        "lag24",
    )
    proportional_hazards_check(cph_lag, model_df_lag, "Model 5 lag24", "lag24")

    main_results = pd.concat(result_frames, ignore_index=True)
    lag_results = clean_summary(summary_lag)
    main_results.to_csv(TABLE_DIR / "cox_msa_allcause_preliminary.csv", index=False)
    lag_results.to_csv(TABLE_DIR / "cox_msa_allcause_lag24_preliminary.csv", index=False)
    pd.concat([plot_data(main_results), plot_data(lag_results)], ignore_index=True).to_csv(
        TABLE_DIR / "msa_dose_response_plot_data.csv",
        index=False,
    )
    write_log(f"{timestamp()} - Preliminary Cox fallback complete. No burden/cost outputs computed.")


if __name__ == "__main__":
    main()
