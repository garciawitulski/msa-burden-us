"""Build the main descriptive Table 1 by MSA guideline status.

This script uses the existing NHIS-LMF complete-case survival cohort and does
not refit models. It writes a reproducible CSV plus a LaTeX table that can be
input directly by the main manuscript.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SURVIVAL_MAIN = PROJECT_ROOT / "data/processed/msa_survival_main_completecase.csv"
OUTPUT_CSV = PROJECT_ROOT / "outputs/tables/manuscript/table1_msa_descriptive_by_exposure.csv"
OUTPUT_TEX = PROJECT_ROOT / "manuscript_latex/tables/table1_msa_descriptive_by_exposure.tex"

USECOLS = [
    "age",
    "age_cat",
    "sex",
    "race_ethnicity",
    "education",
    "poverty",
    "marital_status",
    "region",
    "bmi_cat",
    "smoking_status",
    "alcohol_use",
    "self_rated_health",
    "aerobic_guideline_cat",
    "diabetes",
    "hypertension",
    "cvd_history",
    "cancer_history",
    "insufficient_msa",
    "weight_mortality",
]

GROUPS = [
    ("insufficient", 1.0, "Insufficient MSA (<2 times/week)"),
    ("sufficient", 0.0, "Meeting MSA threshold (>=2 times/week)"),
]

CATEGORY_SPECS = [
    (
        "Age group, years",
        "age_cat",
        [
            ("18-34", "18--34"),
            ("35-44", "35--44"),
            ("45-54", "45--54"),
            ("55-64", "55--64"),
            ("65-74", "65--74"),
            ("75+", "75+"),
        ],
    ),
    ("Sex", "sex", [("Female", "Female"), ("Male", "Male")]),
    (
        "Race/ethnicity",
        "race_ethnicity",
        [
            ("Hispanic", "Hispanic"),
            ("Non-Hispanic American Indian/Alaska Native", "Non-Hispanic American Indian/Alaska Native"),
            ("Non-Hispanic Asian/Pacific Islander", "Non-Hispanic Asian/Pacific Islander"),
            ("Non-Hispanic Black", "Non-Hispanic Black"),
            ("Non-Hispanic Multiple race", "Non-Hispanic multiple race"),
            ("Non-Hispanic Other race", "Non-Hispanic other race"),
            ("Non-Hispanic White", "Non-Hispanic White"),
        ],
    ),
    (
        "Education",
        "education",
        [
            ("Less than high school", "Less than high school"),
            ("High school/GED", "High school/GED"),
            ("Some college/AA", "Some college/AA"),
            ("Bachelor's degree", "Bachelor's degree"),
            ("Graduate/professional degree", "Graduate/professional degree"),
        ],
    ),
    (
        "Poverty-income ratio",
        "poverty",
        [
            ("<1.00 poverty ratio", "<1.00"),
            ("1.00-1.99 poverty ratio", "1.00--1.99"),
            (">=2.00 poverty ratio", ">=2.00"),
        ],
    ),
    (
        "Marital status",
        "marital_status",
        [
            (("Married", "Married - Spouse present", "Married - Spouse not in household"), "Married"),
            ("Never married", "Never married"),
            ("Divorced", "Divorced"),
            ("Separated", "Separated"),
            ("Widowed", "Widowed"),
        ],
    ),
    (
        "Region",
        "region",
        [
            ("Northeast", "Northeast"),
            ("North Central/Midwest", "North Central/Midwest"),
            ("South", "South"),
            ("West", "West"),
        ],
    ),
    (
        "Aerobic physical activity",
        "aerobic_guideline_cat",
        [
            ("inactive", "Inactive"),
            ("insufficiently active", "Insufficiently active"),
            ("meets guideline", "Meets guideline"),
        ],
    ),
    (
        "BMI category",
        "bmi_cat",
        [
            ("underweight", "Underweight"),
            ("normal weight", "Normal weight"),
            ("overweight", "Overweight"),
            ("obesity", "Obesity"),
        ],
    ),
    (
        "Smoking status",
        "smoking_status",
        [
            ("Never smoked", "Never smoked"),
            ("Former smoker", "Former smoker"),
            ("Current every day smoker", "Current every day smoker"),
            ("Current some day smoker", "Current some day smoker"),
        ],
    ),
    (
        "Alcohol use",
        "alcohol_use",
        [
            ("Lifetime abstainer (lt 12 drinks in life)", "Lifetime abstainer"),
            ("Former drinker (no drinks past year)", "Former drinker"),
            ("Current drinker (1+ drinks past year)", "Current drinker"),
        ],
    ),
    (
        "Self-rated health",
        "self_rated_health",
        [
            ("Excellent", "Excellent"),
            ("Very Good", "Very good"),
            ("Good", "Good"),
            ("Fair", "Fair"),
            ("Poor", "Poor"),
        ],
    ),
]

BINARY_SPECS = [
    ("Diabetes", "diabetes"),
    ("Hypertension", "hypertension"),
    ("Cardiovascular disease history", "cvd_history"),
    ("Cancer history", "cancer_history"),
]


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


def fmt_pct(value: float) -> str:
    if pd.isna(value):
        return ""
    return f"{100 * value:.1f}"


def fmt_mean_sd(mean: float, sd: float) -> str:
    if pd.isna(mean) or pd.isna(sd):
        return ""
    return f"{mean:.1f} ({sd:.1f})"


def tex_escape(text: str) -> str:
    replacements = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    out = text
    for old, new in replacements.items():
        out = out.replace(old, new)
    out = out.replace(">=", r"\(\geq\)")
    out = out.replace("<", r"\(<\)")
    return out


def group_frame(df: pd.DataFrame, value: float) -> pd.DataFrame:
    return df.loc[pd.to_numeric(df["insufficient_msa"], errors="coerce") == value].copy()


def group_weights(df: pd.DataFrame) -> pd.Series:
    return pd.to_numeric(df["weight_mortality"], errors="coerce")


def weighted_percent(df: pd.DataFrame, variable: str, level: object) -> str:
    weights = group_weights(df)
    denom = weights.loc[weights.notna() & (weights > 0)].sum()
    values = df[variable]
    if isinstance(level, (tuple, list)):
        mask = values.astype(str).isin([str(item) for item in level])
    else:
        mask = values.astype(str) == str(level)
    numerator = weights.loc[mask & weights.notna() & (weights > 0)].sum()
    return fmt_pct(numerator / denom if denom else np.nan)


def build_rows(df: pd.DataFrame) -> list[dict[str, str]]:
    frames = {name: group_frame(df, group_value) for name, group_value, _ in GROUPS}
    rows: list[dict[str, str]] = []

    rows.append(
        {
            "characteristic": "Unweighted n",
            "insufficient": f"{len(frames['insufficient']):,}",
            "sufficient": f"{len(frames['sufficient']):,}",
            "row_type": "data",
        }
    )
    rows.append(
        {
            "characteristic": "Age, years, mean (SD)",
            "insufficient": fmt_mean_sd(
                weighted_mean(pd.to_numeric(frames["insufficient"]["age"], errors="coerce"), group_weights(frames["insufficient"])),
                weighted_sd(pd.to_numeric(frames["insufficient"]["age"], errors="coerce"), group_weights(frames["insufficient"])),
            ),
            "sufficient": fmt_mean_sd(
                weighted_mean(pd.to_numeric(frames["sufficient"]["age"], errors="coerce"), group_weights(frames["sufficient"])),
                weighted_sd(pd.to_numeric(frames["sufficient"]["age"], errors="coerce"), group_weights(frames["sufficient"])),
            ),
            "row_type": "data",
        }
    )

    for group_label, variable, levels in CATEGORY_SPECS:
        rows.append({"characteristic": group_label, "insufficient": "", "sufficient": "", "row_type": "section"})
        for raw_level, display_level in levels:
            rows.append(
                {
                    "characteristic": display_level,
                    "insufficient": weighted_percent(frames["insufficient"], variable, raw_level),
                    "sufficient": weighted_percent(frames["sufficient"], variable, raw_level),
                    "row_type": "data",
                }
            )

    rows.append({"characteristic": "Clinical history", "insufficient": "", "sufficient": "", "row_type": "section"})
    for display_label, variable in BINARY_SPECS:
        rows.append(
            {
                "characteristic": display_label,
                "insufficient": weighted_percent(frames["insufficient"], variable, 1.0),
                "sufficient": weighted_percent(frames["sufficient"], variable, 1.0),
                "row_type": "data",
            }
        )

    return rows


def write_csv(rows: list[dict[str, str]]) -> None:
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df = df[["characteristic", "insufficient", "sufficient", "row_type"]]
    df.to_csv(OUTPUT_CSV, index=False)


def write_tex(rows: list[dict[str, str]]) -> None:
    OUTPUT_TEX.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        r"\begin{table}[p]",
        r"\centering",
        r"\begingroup",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{4pt}",
        r"\renewcommand{\arraystretch}{0.84}",
        r"\caption{Baseline characteristics of the NHIS-LMF complete-case mortality cohort by MSA guideline status.}",
        r"\label{tab:cohort-characteristics}",
        r"\begin{tabular}{p{0.42\textwidth}p{0.24\textwidth}p{0.24\textwidth}}",
        r"\toprule",
        r"Characteristic & Insufficient MSA (\(<\)2 times/week) & Meeting MSA threshold (\(\geq\)2 times/week) \\",
        r"\midrule",
    ]
    for row in rows:
        if row["row_type"] == "section":
            lines.append(rf"\addlinespace[1pt]\multicolumn{{3}}{{l}}{{\textit{{{tex_escape(row['characteristic'])}}}}} \\")
        else:
            label = tex_escape(row["characteristic"])
            if label not in {"Unweighted n", "Age, years, mean (SD)"}:
                label = rf"\hspace{{0.8em}}{label}"
            lines.append(rf"{label} & {tex_escape(row['insufficient'])} & {tex_escape(row['sufficient'])} \\")
    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\par\vspace{4pt}",
            r"\begin{minipage}{0.95\textwidth}",
            r"\footnotesize Values are weighted percentages using NHIS-LMF mortality weights unless otherwise indicated; n values are unweighted. The complete-case cohort was used to estimate the all-cause mortality hazard ratio. Insufficient MSA was defined as reporting muscle-strengthening activity fewer than 2 times per week; meeting the MSA threshold was defined as reporting 2 or more times per week. BMI = body mass index; MSA = muscle-strengthening activity; NHIS-LMF = National Health Interview Survey Linked Mortality File.",
            r"\end{minipage}",
            r"\endgroup",
            r"\end{table}",
            "",
        ]
    )
    OUTPUT_TEX.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    if not SURVIVAL_MAIN.exists():
        raise SystemExit(f"Required input not found: {SURVIVAL_MAIN.relative_to(PROJECT_ROOT)}")
    chunks = pd.read_csv(SURVIVAL_MAIN, usecols=USECOLS, chunksize=50_000)
    df = pd.concat(chunks, ignore_index=True)
    df = df.loc[pd.to_numeric(df["insufficient_msa"], errors="coerce").isin([0.0, 1.0])].copy()
    rows = build_rows(df)
    write_csv(rows)
    write_tex(rows)
    print(f"Wrote {OUTPUT_CSV.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {OUTPUT_TEX.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
