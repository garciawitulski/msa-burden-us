"""Create reviewer-revision summary tables.

This script formats diagnostics that are not part of the original burden
pipeline but are needed for the reviewer response: complete-case attrition
under alternative covariate sets and Cox sensitivity estimates.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "data/processed"
TABLE_DIR = PROJECT_ROOT / "outputs/tables"

FULL_DATA = PROCESSED_DIR / "msa_survival_full.csv"
REVIEWER_COX = TABLE_DIR / "reviewer_cox_sensitivity.csv"
MISSINGNESS_CSV = TABLE_DIR / "reviewer_missingness_impact.csv"
MISSINGNESS_MD = TABLE_DIR / "reviewer_missingness_impact.md"
REVIEWER_COX_MD = TABLE_DIR / "reviewer_cox_sensitivity.md"


CURRENT_COVARIATES = [
    "aerobic_category",
    "poverty",
    "bmi_cat",
    "alcohol_use",
    "diabetes",
    "education",
    "smoking_status",
    "marital_status",
    "cvd_history",
    "hypertension",
    "cancer_history",
    "self_rated_health",
    "race_ethnicity",
]


def fmt_int(value: float | int) -> str:
    return f"{float(value):,.0f}"


def fmt_pct(value: float | int, digits: int = 1) -> str:
    return f"{float(value):.{digits}f}"


def df_to_markdown(df: pd.DataFrame, title: str, note: str) -> str:
    lines = [f"# {title}", ""]
    lines.append("| " + " | ".join(df.columns) + " |")
    lines.append("| " + " | ".join(["---"] * len(df.columns)) + " |")
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(row[col]) for col in df.columns) + " |")
    lines.extend(["", f"Note: {note}", ""])
    return "\n".join(lines)


def make_missingness_impact() -> pd.DataFrame:
    usecols = ["nonmissing_followup", "msa_guideline", *CURRENT_COVARIATES]
    df = pd.read_csv(FULL_DATA, usecols=usecols, low_memory=False)
    base = df["nonmissing_followup"].eq(1)
    msa = base & df["msa_guideline"].notna()
    base_n = int(msa.sum())

    rows: list[dict[str, object]] = []
    scenarios = [
        ("Current complete-case model", []),
        ("Omit poverty-income ratio", ["poverty"]),
        ("Omit BMI category", ["bmi_cat"]),
        ("Omit aerobic-activity category", ["aerobic_category"]),
        ("Omit PIR and BMI", ["poverty", "bmi_cat"]),
        ("Omit PIR and aerobic activity", ["poverty", "aerobic_category"]),
        ("Omit BMI and aerobic activity", ["bmi_cat", "aerobic_category"]),
        ("Omit PIR, BMI, and aerobic activity", ["poverty", "bmi_cat", "aerobic_category"]),
    ]
    current_mask = msa.copy()
    for covariate in CURRENT_COVARIATES:
        current_mask &= df[covariate].notna()
    current_n = int(current_mask.sum())
    for label, omitted in scenarios:
        mask = msa.copy()
        for covariate in CURRENT_COVARIATES:
            if covariate not in omitted:
                mask &= df[covariate].notna()
        n = int(mask.sum())
        rows.append(
            {
                "scenario": label,
                "omitted_covariates": ", ".join(omitted) if omitted else "none",
                "analytic_n": fmt_int(n),
                "percent_of_nonmissing_msa": fmt_pct(n / base_n * 100),
                "gain_vs_current_n": fmt_int(n - current_n),
            }
        )

    out = pd.DataFrame(rows)
    out.to_csv(MISSINGNESS_CSV, index=False)
    MISSINGNESS_MD.write_text(
        df_to_markdown(
            out,
            "Reviewer Missingness Impact",
            "Base denominator is 628,141 mortality-linkage-eligible adults with non-missing MSA and follow-up.",
        ),
        encoding="utf-8",
    )
    return out


def make_reviewer_cox_markdown() -> pd.DataFrame:
    if not REVIEWER_COX.exists():
        raise SystemExit(f"Missing {REVIEWER_COX.relative_to(PROJECT_ROOT)}. Run code/stata/04_reviewer_cox_sensitivity.do first.")
    df = pd.read_csv(REVIEWER_COX)
    for col in ["hazard_ratio", "ci_lower", "ci_upper", "p_value"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    display = pd.DataFrame(
        {
            "scenario": df["scenario"],
            "design": df["design_type"],
            "n": df["n_obs"].map(lambda x: fmt_int(float(x))),
            "events": df["n_fail"].map(lambda x: fmt_int(float(x))),
            "HR_95_CI": [
                "" if pd.isna(hr) else f"{hr:.3f} ({lo:.3f}-{hi:.3f})"
                for hr, lo, hi in zip(df["hazard_ratio"], df["ci_lower"], df["ci_upper"])
            ],
            "p_value": ["" if pd.isna(p) else ("<0.001" if p < 0.001 else f"{p:.3f}") for p in df["p_value"]],
            "status": df["status"],
        }
    )
    REVIEWER_COX_MD.write_text(
        df_to_markdown(
            display,
            "Reviewer Cox Sensitivity Models",
            "Target models use premature mortality failure before age 70. The Taylor model uses svyset PSU/STRATA with mortality weights.",
        )
        + f"\nGenerated: {datetime.now().isoformat(timespec='seconds')}\n",
        encoding="utf-8",
    )
    return display


def main() -> None:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    missing = make_missingness_impact()
    cox = make_reviewer_cox_markdown()
    print(f"Wrote {MISSINGNESS_CSV.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {MISSINGNESS_MD.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {REVIEWER_COX_MD.relative_to(PROJECT_ROOT)}")
    print(f"Rows: missingness={len(missing)}, cox={len(cox)}")


if __name__ == "__main__":
    main()
