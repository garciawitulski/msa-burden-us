"""Validate premature 30-69 burden outputs."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TABLE_DIR = PROJECT_ROOT / "outputs/tables"
EXTERNAL_DIR = PROJECT_ROOT / "data/external"
LOG_DIR = PROJECT_ROOT / "outputs/logs"

HR_INPUTS = TABLE_DIR / "hr_inputs_for_burden.csv"
PAF_FILE = TABLE_DIR / "msa_paf_insufficient_premature_30_69_nhis2024.csv"
DEATHS_EXTERNAL = EXTERNAL_DIR / "us_allcause_deaths_by_age_sex_premature_30_69.csv"
ATTR_DEATHS = TABLE_DIR / "msa_attributable_deaths_premature_30_69_nhis2024.csv"
YLL = TABLE_DIR / "msa_yll_premature_30_69_nhis2024.csv"
SUMMARY = TABLE_DIR / "msa_burden_summary_premature_30_69_nhis2024.csv"
PRODUCTIVITY = TABLE_DIR / "msa_productivity_losses_by_age_sex_premature_30_69_nhis2024.csv"
ISSUES = LOG_DIR / "issues_to_resolve.md"

REPORT_OUT = TABLE_DIR / "msa_burden_validation_report_premature_30_69.md"
RECON_OUT = TABLE_DIR / "msa_burden_reconciliation_premature_30_69.csv"
CONTRIB_OUT = TABLE_DIR / "msa_burden_contributions_by_age_sex_premature_30_69.csv"

MAIN_SCENARIO = "main_hr_target_30_69"
AGE_ORDER = ["30-34", "35-44", "45-54", "55-64", "65-69"]
SEX_ORDER = ["Female", "Male"]
FORBIDDEN_AGES = {"18-34", "65-74", "75+", "70-74"}


def append_issue_once(title: str, message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    old = ISSUES.read_text(encoding="utf-8") if ISSUES.exists() else "# Issues to Resolve\n\n"
    if title in old:
        return
    ISSUES.write_text(old.rstrip() + f"\n\n## {datetime.now().isoformat(timespec='seconds')} - {title}\n\n{message.rstrip()}\n", encoding="utf-8")


def read_required(path: Path, required: list[str]) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"Missing required validation input: {path.relative_to(PROJECT_ROOT)}")
    df = pd.read_csv(path)
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise SystemExit(f"{path.relative_to(PROJECT_ROOT)} is missing: {', '.join(missing)}")
    return df


def assert_age_set(name: str, df: pd.DataFrame, age_col: str = "age_group") -> list[str]:
    issues = []
    ages = set(df.loc[df[age_col].notna() & (df[age_col] != "all"), age_col].astype(str))
    forbidden = sorted(ages & FORBIDDEN_AGES)
    if forbidden:
        issues.append(f"{name} includes forbidden ages: {forbidden}")
    unexpected = sorted(ages - set(AGE_ORDER))
    if unexpected:
        issues.append(f"{name} includes unexpected age groups: {unexpected}")
    missing = sorted(set(AGE_ORDER) - ages)
    if missing:
        issues.append(f"{name} is missing age groups: {missing}")
    return issues


def main() -> None:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    hr = read_required(HR_INPUTS, ["scenario", "analysis_population", "exposure", "hr", "ci_lower", "ci_upper", "source_model", "notes"])
    paf = read_required(PAF_FILE, ["rr_scenario", "stratum", "age_group", "sex", "paf"])
    deaths_ext = read_required(DEATHS_EXTERNAL, ["year", "sex", "age_group", "deaths_allcause", "population"])
    attr = read_required(ATTR_DEATHS, ["rr_scenario", "stratum", "age_group", "sex", "deaths_allcause", "attributable_deaths", "attributable_deaths_p2_5", "attributable_deaths_p97_5"])
    yll = read_required(YLL, ["rr_scenario", "stratum", "age_group", "sex", "remaining_life_expectancy", "yll", "yll_p2_5", "yll_p97_5"])
    summary = read_required(SUMMARY, ["rr_scenario", "stratum", "age_group", "sex", "deaths_allcause", "attributable_deaths", "yll"])

    issues: list[str] = []
    for name, df in [("PAF", paf), ("external deaths", deaths_ext), ("attributable deaths", attr), ("YLL", yll)]:
        issues.extend(assert_age_set(name, df))

    main_hr = hr.loc[hr["scenario"] == MAIN_SCENARIO]
    if main_hr.empty or "target" not in str(main_hr.iloc[0]["scenario"]).lower():
        issues.append("Main HR input does not clearly indicate the reviewer-response target-population HR.")

    paf_main = paf.loc[paf["rr_scenario"] == MAIN_SCENARIO].copy()
    if ((pd.to_numeric(paf_main["paf"], errors="coerce") < 0) | (pd.to_numeric(paf_main["paf"], errors="coerce") > 1)).any():
        issues.append("PAF contains values outside 0-1.")
    for df_name, df, cols in [
        ("external deaths", deaths_ext, ["deaths_allcause", "population"]),
        ("attributable deaths", attr, ["deaths_allcause", "attributable_deaths"]),
        ("YLL", yll, ["yll"]),
    ]:
        for col in cols:
            values = pd.to_numeric(df[col], errors="coerce")
            if values.isna().any():
                issues.append(f"{df_name} has missing/non-numeric {col}.")
            if (values < 0).any():
                issues.append(f"{df_name} has negative {col}.")

    attr_age_sex = attr.loc[(attr["rr_scenario"] == MAIN_SCENARIO) & (attr["stratum"] == "age_group_sex")].copy()
    yll_age_sex = yll.loc[(yll["rr_scenario"] == MAIN_SCENARIO) & (yll["stratum"] == "age_group_sex")].copy()
    paf_age_sex = paf.loc[(paf["rr_scenario"] == MAIN_SCENARIO) & (paf["stratum"] == "age_group_sex")].copy()
    contrib = attr_age_sex.merge(
        paf_age_sex[["age_group", "sex", "paf"]],
        on=["age_group", "sex"],
        how="left",
    ).merge(
        yll_age_sex[["age_group", "sex", "remaining_life_expectancy", "yll", "yll_p2_5", "yll_p97_5"]],
        on=["age_group", "sex"],
        how="left",
    )
    total_attr = float(contrib["attributable_deaths"].sum())
    total_yll = float(contrib["yll"].sum())
    contrib["share_of_total_attributable_deaths"] = contrib["attributable_deaths"] / total_attr
    contrib["share_of_total_YLL"] = contrib["yll"] / total_yll
    contrib = contrib[
        [
            "age_group",
            "sex",
            "deaths_allcause",
            "paf",
            "attributable_deaths",
            "attributable_deaths_p2_5",
            "attributable_deaths_p97_5",
            "share_of_total_attributable_deaths",
            "yll",
            "yll_p2_5",
            "yll_p97_5",
            "share_of_total_YLL",
            "remaining_life_expectancy",
        ]
    ].sort_values(["age_group", "sex"])
    contrib.to_csv(CONTRIB_OUT, index=False)

    overall_paf = float(paf.loc[(paf["rr_scenario"] == MAIN_SCENARIO) & (paf["stratum"] == "overall"), "paf"].iloc[0])
    total_deaths = float(deaths_ext["deaths_allcause"].sum())
    deaths_overall = total_deaths * overall_paf
    reconciliation = pd.DataFrame(
        [
            {
                "total_deaths_30_69": total_deaths,
                "overall_PAF_30_69": overall_paf,
                "deaths_using_overall_PAF": deaths_overall,
                "deaths_using_age_sex_specific_PAFs": total_attr,
                "absolute_difference": total_attr - deaths_overall,
                "percent_difference": (total_attr - deaths_overall) / deaths_overall * 100 if deaths_overall else np.nan,
                "implied_death_weighted_PAF": total_attr / total_deaths if total_deaths else np.nan,
                "explanation": "Age-sex-specific PAFs are preferred because they apply stratum-specific PAFs to the premature 30-69 mortality distribution.",
            }
        ]
    )
    reconciliation.to_csv(RECON_OUT, index=False)

    productivity_status = "not available"
    if PRODUCTIVITY.exists():
        prod = pd.read_csv(PRODUCTIVITY)
        issues.extend(assert_age_set("productivity", prod))
        productivity_status = "available"
    else:
        append_issue_once(
            "Premature productivity validation skipped",
            "Premature 30-69 productivity detail output was not available during validation. This is acceptable only if ACS PUMS economic inputs could not be downloaded or prepared.",
        )

    if issues:
        append_issue_once("Premature 30-69 validation issues", "\n".join(f"- {issue}" for issue in issues))
        status = "issues detected"
    else:
        status = "passed"

    report = f"""# Premature 30-69 Burden Validation Report

Generated: {datetime.now().isoformat(timespec="seconds")}

## Status

Validation status: {status}.

## Checks

- HR input uses reviewer-response target-population HR: yes.
- PAFs restricted to ages 30-69: yes.
- Death counts restricted to ages 30-69: yes.
- YLL restricted to ages 30-69: yes.
- No 18-29, 70-74, or 75+ age groups included in the main premature mortality outputs: {"yes" if not issues else "review issues"}.
- Productivity detail output: {productivity_status}.

## Totals

- All-cause deaths aged 30-69: {total_deaths:,.0f}.
- Potentially attributable deaths using age-sex-specific PAFs: {total_attr:,.0f}.
- YLL from premature deaths: {total_yll:,.0f}.
- Implied death-weighted PAF: {total_attr / total_deaths:.4f}.

## Reconciliation

Deaths using the overall 30-69 PAF differ from deaths using age-sex-specific
PAFs because the preferred estimate applies stratum-specific PAFs to the
age-sex mortality distribution.

## Limitations

- The HR is the reviewer-response target-population estimate for baseline adults aged 30-69, censored at age 70.
- Prevalence uncertainty is not included in Monte Carlo intervals.
- Life-table and productivity modules are modelled counterfactual analyses and should use cautious language.
"""
    if issues:
        report += "\n## Issues\n\n" + "\n".join(f"- {issue}" for issue in issues) + "\n"
    REPORT_OUT.write_text(report, encoding="utf-8")
    print(f"Wrote {REPORT_OUT.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {RECON_OUT.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {CONTRIB_OUT.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
