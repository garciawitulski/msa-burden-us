"""Validate and reconcile NHIS 2024 attributable deaths and YLL outputs.

This audit checks internal consistency before any productivity-cost work. It
does not compute productivity losses, life expectancy gains, or costs.
"""

from __future__ import annotations

import math
import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TABLE_DIR = PROJECT_ROOT / "outputs/tables"
EXTERNAL_DIR = PROJECT_ROOT / "data/external"
LOG_DIR = PROJECT_ROOT / "outputs/logs"

PAF_FILE = TABLE_DIR / "msa_paf_insufficient_using_nhis2024.csv"
PAF_MC_FILE = TABLE_DIR / "msa_paf_insufficient_montecarlo_using_nhis2024.csv"
ATTR_DEATHS_FILE = TABLE_DIR / "msa_attributable_deaths_nhis2024.csv"
YLL_FILE = TABLE_DIR / "msa_yll_nhis2024.csv"
SUMMARY_FILE = TABLE_DIR / "msa_burden_summary_nhis2024.csv"
DEATHS_EXTERNAL_FILE = EXTERNAL_DIR / "us_allcause_deaths_by_age_sex.csv"
LIFE_EXTERNAL_FILE = EXTERNAL_DIR / "us_life_table_by_agegroup_sex.csv"
READINESS_REPORT = TABLE_DIR / "burden_readiness_report.md"
ISSUES = LOG_DIR / "issues_to_resolve.md"

RECONCILIATION_OUT = TABLE_DIR / "msa_burden_reconciliation_nhis2024.csv"
CONTRIBUTIONS_OUT = TABLE_DIR / "msa_burden_contributions_by_age_sex.csv"
VALIDATION_REPORT = TABLE_DIR / "msa_burden_validation_report.md"

TARGET_PERIOD = "nhis_2024_current"
PRIMARY_SCENARIO = "main_strata_sex_year"
TARGET_AGE_GROUPS = ["18-34", "35-44", "45-54", "55-64", "65-74", "75+"]
TARGET_SEXES = ["Female", "Male"]
REL_TOL = 1e-8
ABS_TOL = 1e-4


def ensure_dirs() -> None:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def append_issue_once(title: str, message: str) -> None:
    ensure_dirs()
    old = ISSUES.read_text(encoding="utf-8") if ISSUES.exists() else "# Issues to Resolve\n\n"
    if title in old:
        return
    ISSUES.write_text(
        old.rstrip() + f"\n\n## {datetime.now().isoformat(timespec='seconds')} - {title}\n\n{message.rstrip()}\n",
        encoding="utf-8",
    )


def stop(title: str, message: str) -> None:
    append_issue_once(title, message)
    raise SystemExit(message)


def read_required(path: Path, required: list[str]) -> pd.DataFrame:
    if not path.exists():
        stop("Missing validation input", f"`{path.relative_to(PROJECT_ROOT)}` was not found.")
    df = pd.read_csv(path)
    missing = [col for col in required if col not in df.columns]
    if missing:
        stop(
            "Validation input missing required columns",
            f"`{path.relative_to(PROJECT_ROOT)}` is missing required columns: {', '.join(missing)}.",
        )
    return df


def numeric(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in columns:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def close_enough(a: float, b: float, abs_tol: float = ABS_TOL) -> bool:
    return math.isclose(float(a), float(b), rel_tol=REL_TOL, abs_tol=abs_tol)


def filter_primary(df: pd.DataFrame, stratum: str | None = None) -> pd.DataFrame:
    out = df.loc[(df["target_period"] == TARGET_PERIOD) & (df["rr_scenario"] == PRIMARY_SCENARIO)].copy()
    if stratum is not None:
        out = out.loc[out["stratum"] == stratum].copy()
    return out


def expected_pairs() -> set[tuple[str, str]]:
    return {(age, sex) for age in TARGET_AGE_GROUPS for sex in TARGET_SEXES}


def check_pairs(df: pd.DataFrame, label: str, failures: list[str]) -> None:
    found = set(zip(df["age_group"].astype(str), df["sex"].astype(str)))
    missing = sorted(expected_pairs() - found)
    extra = sorted(found - expected_pairs())
    if missing:
        failures.append(f"{label} is missing age-sex strata: {missing}")
    if extra:
        failures.append(f"{label} has unexpected age-sex strata: {extra}")


def load_inputs() -> dict[str, pd.DataFrame]:
    return {
        "paf": read_required(
            PAF_FILE,
            ["target_period", "stratum", "age_group", "sex", "rr_scenario", "prevalence_insufficient_msa", "paf"],
        ),
        "mc": read_required(
            PAF_MC_FILE,
            ["target_period", "stratum", "age_group", "sex", "rr_scenario", "n_draws", "paf_median", "paf_p2_5", "paf_p97_5"],
        ),
        "attr": read_required(
            ATTR_DEATHS_FILE,
            [
                "target_period",
                "stratum",
                "age_group",
                "sex",
                "rr_scenario",
                "deaths_allcause",
                "attributable_deaths",
                "attributable_deaths_p2_5",
                "attributable_deaths_p97_5",
            ],
        ),
        "yll": read_required(
            YLL_FILE,
            ["target_period", "stratum", "age_group", "sex", "rr_scenario", "deaths_allcause", "remaining_life_expectancy", "yll", "yll_p2_5", "yll_p97_5"],
        ),
        "summary": read_required(
            SUMMARY_FILE,
            [
                "target_period",
                "stratum",
                "age_group",
                "sex",
                "rr_scenario",
                "deaths_allcause",
                "attributable_deaths",
                "attributable_deaths_p2_5",
                "attributable_deaths_p97_5",
                "yll",
                "yll_p2_5",
                "yll_p97_5",
            ],
        ),
        "external_deaths": read_required(DEATHS_EXTERNAL_FILE, ["year", "sex", "age_group", "deaths_allcause", "population"]),
        "external_life": read_required(LIFE_EXTERNAL_FILE, ["year", "sex", "age_group", "remaining_life_expectancy"]),
    }


def build_merged(inputs: dict[str, pd.DataFrame], failures: list[str]) -> pd.DataFrame:
    paf_age_sex = numeric(filter_primary(inputs["paf"], "age_group_sex"), ["prevalence_insufficient_msa", "paf"])
    attr_age_sex = numeric(filter_primary(inputs["attr"], "age_group_sex"), ["deaths_allcause", "attributable_deaths"])
    yll_age_sex = numeric(filter_primary(inputs["yll"], "age_group_sex"), ["yll", "remaining_life_expectancy"])
    external_deaths = numeric(inputs["external_deaths"], ["deaths_allcause", "population"])
    external_life = numeric(inputs["external_life"], ["remaining_life_expectancy"])
    mc_age_sex = numeric(filter_primary(inputs["mc"], "age_group_sex"), ["n_draws", "paf_median", "paf_p2_5", "paf_p97_5"])

    for label, frame in [
        ("PAF table", paf_age_sex),
        ("attributable deaths table", attr_age_sex),
        ("YLL table", yll_age_sex),
        ("external deaths table", external_deaths),
        ("external life table", external_life),
        ("Monte Carlo PAF table", mc_age_sex),
    ]:
        check_pairs(frame, label, failures)

    merged = paf_age_sex[["age_group", "sex", "prevalence_insufficient_msa", "paf"]].merge(
        external_deaths[["age_group", "sex", "deaths_allcause", "population"]],
        on=["age_group", "sex"],
        how="left",
    )
    merged = merged.merge(
        external_life[["age_group", "sex", "remaining_life_expectancy"]],
        on=["age_group", "sex"],
        how="left",
    )
    merged = merged.merge(
        attr_age_sex[["age_group", "sex", "attributable_deaths"]],
        on=["age_group", "sex"],
        how="left",
    )
    merged = merged.merge(yll_age_sex[["age_group", "sex", "yll"]], on=["age_group", "sex"], how="left")
    merged = merged.merge(
        mc_age_sex[["age_group", "sex", "n_draws", "paf_median", "paf_p2_5", "paf_p97_5"]],
        on=["age_group", "sex"],
        how="left",
    )

    if merged[["paf", "deaths_allcause", "remaining_life_expectancy", "attributable_deaths", "yll"]].isna().any().any():
        failures.append("At least one age-sex row has missing PAF, death count, life expectancy, attributable deaths, or YLL.")
    if (merged["deaths_allcause"] < 0).any():
        failures.append("At least one age-sex row has negative all-cause deaths.")
    if (merged["attributable_deaths"] < 0).any():
        failures.append("At least one age-sex row has negative attributable deaths.")
    if (merged["yll"] < 0).any():
        failures.append("At least one age-sex row has negative YLL.")
    if ((merged["paf"] < 0) | (merged["paf"] > 1)).any():
        failures.append("At least one age-sex row has an impossible PAF outside [0, 1].")
    if ((merged["paf_p2_5"] > merged["paf_median"]) | (merged["paf_median"] > merged["paf_p97_5"])).any():
        failures.append("At least one Monte Carlo PAF percentile row is not ordered p2.5 <= median <= p97.5.")
    if (merged["n_draws"] < 10000).any():
        failures.append("At least one Monte Carlo row has fewer than 10,000 draws.")

    merged["expected_attributable_deaths"] = merged["paf"] * merged["deaths_allcause"]
    merged["attributable_deaths_abs_diff"] = (merged["expected_attributable_deaths"] - merged["attributable_deaths"]).abs()
    merged["expected_yll"] = merged["attributable_deaths"] * merged["remaining_life_expectancy"]
    merged["yll_abs_diff"] = (merged["expected_yll"] - merged["yll"]).abs()
    if merged["attributable_deaths_abs_diff"].max(skipna=True) > 1e-6:
        failures.append("Attributable deaths are not exactly equal to age-sex PAF times age-sex all-cause deaths.")
    if merged["yll_abs_diff"].max(skipna=True) > 1e-6:
        failures.append("YLL is not exactly equal to attributable deaths times remaining life expectancy.")

    return merged


def scalar_from(frame: pd.DataFrame, column: str, label: str, failures: list[str]) -> float:
    if len(frame) != 1:
        failures.append(f"Expected exactly one {label} row; found {len(frame)}.")
        return np.nan
    return float(pd.to_numeric(frame[column], errors="coerce").iloc[0])


def build_validation_outputs(inputs: dict[str, pd.DataFrame], merged: pd.DataFrame, failures: list[str]) -> dict[str, float]:
    paf_overall = numeric(filter_primary(inputs["paf"], "overall"), ["paf"])
    attr_overall = numeric(filter_primary(inputs["attr"], "overall"), ["deaths_allcause", "attributable_deaths", "attributable_deaths_p2_5", "attributable_deaths_p97_5"])
    yll_overall = numeric(filter_primary(inputs["yll"], "overall"), ["yll", "yll_p2_5", "yll_p97_5"])
    summary_overall = numeric(filter_primary(inputs["summary"], "overall"), ["deaths_allcause", "attributable_deaths", "attributable_deaths_p2_5", "attributable_deaths_p97_5", "yll", "yll_p2_5", "yll_p97_5"])

    overall_paf = scalar_from(paf_overall, "paf", "overall PAF", failures)
    total_deaths_external = float(merged["deaths_allcause"].sum())
    total_deaths_attr_table = scalar_from(attr_overall, "deaths_allcause", "overall attributable deaths", failures)
    total_deaths_summary = scalar_from(summary_overall, "deaths_allcause", "summary", failures)
    total_attr_age_sex = float(merged["attributable_deaths"].sum())
    total_attr_overall = scalar_from(attr_overall, "attributable_deaths", "overall attributable deaths", failures)
    total_attr_summary = scalar_from(summary_overall, "attributable_deaths", "summary attributable deaths", failures)
    total_yll_age_sex = float(merged["yll"].sum())
    total_yll_overall = scalar_from(yll_overall, "yll", "overall YLL", failures)
    total_yll_summary = scalar_from(summary_overall, "yll", "summary YLL", failures)

    checks = {
        "external deaths vs attributable-deaths overall row": (total_deaths_external, total_deaths_attr_table),
        "external deaths vs summary row": (total_deaths_external, total_deaths_summary),
        "age-sex attributable deaths vs overall row": (total_attr_age_sex, total_attr_overall),
        "age-sex attributable deaths vs summary row": (total_attr_age_sex, total_attr_summary),
        "age-sex YLL vs overall row": (total_yll_age_sex, total_yll_overall),
        "age-sex YLL vs summary row": (total_yll_age_sex, total_yll_summary),
    }
    for label, (a, b) in checks.items():
        if not close_enough(a, b):
            failures.append(f"Internal total mismatch for {label}: {a} vs {b}.")

    deaths_using_overall_paf = total_deaths_external * overall_paf
    implied_death_weighted_paf = total_attr_age_sex / total_deaths_external
    abs_diff = total_attr_age_sex - deaths_using_overall_paf
    pct_diff = 100 * abs_diff / deaths_using_overall_paf if deaths_using_overall_paf else np.nan
    average_yll_per_attr_death = total_yll_age_sex / total_attr_age_sex

    reconciliation = pd.DataFrame(
        [
            {
                "total_deaths": total_deaths_external,
                "overall_PAF": overall_paf,
                "deaths_using_overall_PAF": deaths_using_overall_paf,
                "deaths_using_age_sex_specific_PAFs": total_attr_age_sex,
                "absolute_difference": abs_diff,
                "percent_difference": pct_diff,
                "implied_death_weighted_PAF": implied_death_weighted_paf,
                "explanation": "Age-sex-specific PAFs are applied to the mortality distribution; the overall PAF is prevalence-weighted in NHIS 2024 and is not death-weighted.",
            }
        ]
    )
    reconciliation.to_csv(RECONCILIATION_OUT, index=False)

    contributions = merged[
        [
            "age_group",
            "sex",
            "deaths_allcause",
            "paf",
            "attributable_deaths",
            "yll",
            "remaining_life_expectancy",
        ]
    ].copy()
    contributions["share_of_total_attributable_deaths"] = contributions["attributable_deaths"] / total_attr_age_sex
    contributions["share_of_total_YLL"] = contributions["yll"] / total_yll_age_sex
    contributions["age_group"] = pd.Categorical(contributions["age_group"], categories=TARGET_AGE_GROUPS, ordered=True)
    contributions = contributions.sort_values(["age_group", "sex"]).reset_index(drop=True)
    contributions["age_group"] = contributions["age_group"].astype(str)
    contributions.to_csv(CONTRIBUTIONS_OUT, index=False)

    return {
        "overall_paf": overall_paf,
        "total_deaths": total_deaths_external,
        "deaths_using_overall_paf": deaths_using_overall_paf,
        "total_attr_deaths": total_attr_age_sex,
        "total_yll": total_yll_age_sex,
        "absolute_difference": abs_diff,
        "percent_difference": pct_diff,
        "implied_death_weighted_paf": implied_death_weighted_paf,
        "average_yll_per_attr_death": average_yll_per_attr_death,
        "attr_p2_5": scalar_from(summary_overall, "attributable_deaths_p2_5", "summary death lower interval", failures),
        "attr_p97_5": scalar_from(summary_overall, "attributable_deaths_p97_5", "summary death upper interval", failures),
        "yll_p2_5": scalar_from(summary_overall, "yll_p2_5", "summary YLL lower interval", failures),
        "yll_p97_5": scalar_from(summary_overall, "yll_p97_5", "summary YLL upper interval", failures),
    }


def top_lines(df: pd.DataFrame, value_col: str, share_col: str, n: int = 5) -> str:
    rows = df.sort_values(value_col, ascending=False).head(n)
    lines = []
    for _, row in rows.iterrows():
        lines.append(
            f"- {row['age_group']} {row['sex']}: {row[value_col]:,.0f} "
            f"({100 * row[share_col]:.1f}%)"
        )
    return "\n".join(lines)


def write_report(metrics: dict[str, float], contributions: pd.DataFrame, failures: list[str]) -> None:
    ready = len(failures) == 0
    top_deaths = top_lines(contributions, "attributable_deaths", "share_of_total_attributable_deaths")
    top_yll = top_lines(contributions, "yll", "share_of_total_YLL")
    validation_status = "pass" if ready else "issues found"
    ready_text = (
        "The outputs are internally consistent and ready for draft manuscript tables, with cautious model-based language."
        if ready
        else "The outputs are not ready for manuscript tables until the validation issues listed below are resolved."
    )
    failure_text = "None." if ready else "\n".join(f"- {failure}" for failure in failures)
    report = f"""# NHIS 2024 Burden Validation Report

Generated: {datetime.now().isoformat(timespec="seconds")}

## Validation status

- Status: {validation_status}
- Total all-cause deaths across age-sex strata: {metrics['total_deaths']:,.0f}
- Total attributable deaths: {metrics['total_attr_deaths']:,.0f}
- Total YLL: {metrics['total_yll']:,.0f}
- Average YLL per attributable death: {metrics['average_yll_per_attr_death']:.2f}
- Implied death-weighted PAF: {metrics['implied_death_weighted_paf']:.4f}
- Overall NHIS 2024 prevalence-based PAF: {metrics['overall_paf']:.4f}

## Internal consistency

The totals are internally consistent if all checks pass. The script verifies
that age-sex deaths sum to the reported overall deaths, that attributable
deaths equal PAF times death counts, and that YLL equals attributable deaths
times remaining life expectancy.

Validation issues:

{failure_text}

## Overall PAF vs age-sex PAFs

Deaths using the overall NHIS 2024 PAF: {metrics['deaths_using_overall_paf']:,.0f}

Deaths using age-sex-specific PAFs: {metrics['total_attr_deaths']:,.0f}

Absolute difference: {metrics['absolute_difference']:,.0f}

Percent difference: {metrics['percent_difference']:.1f}%

These differ because the overall PAF is based on overall NHIS 2024 exposure
prevalence, while the burden calculation applies age-sex-specific PAFs to the
age-sex mortality distribution. Older strata have higher mortality counts and
somewhat higher PAFs, so the death-weighted PAF is higher than the overall
prevalence-weighted PAF.

## Largest Contributors To Attributable Deaths

{top_deaths}

## Largest Contributors To YLL

{top_yll}

## Manuscript Readiness

{ready_text}

Use cautious comparative-risk-assessment language: deaths and YLL are
potentially attributable under the modelled counterfactual, not proven to be
caused by insufficient MSA.

## Limitations

- HRs come from NHIS-LMF 1997-2018, while prevalence is from NHIS 2024.
- Mortality inputs use final CDC WONDER 2024 death counts; YLL uses NCHS United States Life Tables 2023.
- Life expectancy for age groups uses representative ages, including age 80 for 75+.
- Monte Carlo uncertainty reflects HR uncertainty with prevalence treated as fixed.
- Survey-based prevalence uncertainty and productivity costs are not included.
- The age-sex-specific PAF approach is preferred for burden totals; overall PAF estimates are useful for reconciliation only.
"""
    VALIDATION_REPORT.write_text(report, encoding="utf-8")


def replace_marked_section(path: Path, title: str, content: str) -> None:
    start = f"<!-- BEGIN {title} -->"
    end = f"<!-- END {title} -->"
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    block = f"{start}\n{content.rstrip()}\n{end}\n"
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end) + r"\n?", flags=re.S)
    if pattern.search(old):
        new = pattern.sub(block, old)
    else:
        new = old.rstrip() + "\n\n" + block
    path.write_text(new, encoding="utf-8")


def update_readiness(metrics: dict[str, float], failures: list[str]) -> None:
    status = "passed" if not failures else "failed"
    content = f"""## Burden Output Validation

- Validation status: {status}.
- Reconciliation table: `outputs/tables/msa_burden_reconciliation_nhis2024.csv`.
- Age-sex contribution table: `outputs/tables/msa_burden_contributions_by_age_sex.csv`.
- Validation report: `outputs/tables/msa_burden_validation_report.md`.
- Implied death-weighted PAF: {metrics['implied_death_weighted_paf']:.4f}.
- Overall NHIS 2024 PAF: {metrics['overall_paf']:.4f}.
- Age-sex-specific attributable deaths: {metrics['total_attr_deaths']:,.0f}.
- Total YLL: {metrics['total_yll']:,.0f}.

The age-sex-specific burden total is preferred for manuscript tables because it
applies stratum-specific PAFs to the mortality distribution. Productivity costs
were not calculated in this validation step.
"""
    replace_marked_section(READINESS_REPORT, "NHIS2024_BURDEN_VALIDATION", content)


def main() -> None:
    ensure_dirs()
    failures: list[str] = []
    inputs = load_inputs()
    if PRIMARY_SCENARIO not in set(inputs["paf"]["rr_scenario"]):
        stop("Primary burden scenario missing", f"`{PRIMARY_SCENARIO}` was not found in the NHIS 2024 PAF table.")
    if "lag24_strata_sex_year" not in set(inputs["paf"]["rr_scenario"]):
        failures.append("Lag24 sensitivity scenario is missing from the NHIS 2024 PAF table.")

    merged = build_merged(inputs, failures)
    metrics = build_validation_outputs(inputs, merged, failures)
    contributions = pd.read_csv(CONTRIBUTIONS_OUT)
    write_report(metrics, contributions, failures)
    update_readiness(metrics, failures)

    if failures:
        append_issue_once(
            "NHIS 2024 burden validation issues",
            "The validation script found issues:\n\n" + "\n".join(f"- {failure}" for failure in failures),
        )
        raise SystemExit("Validation completed with issues. See outputs/tables/msa_burden_validation_report.md")

    print(f"Created: {RECONCILIATION_OUT.relative_to(PROJECT_ROOT)}")
    print(f"Created: {CONTRIBUTIONS_OUT.relative_to(PROJECT_ROOT)}")
    print(f"Created: {VALIDATION_REPORT.relative_to(PROJECT_ROOT)}")
    print(f"Total all-cause deaths: {metrics['total_deaths']:.0f}")
    print(f"Total attributable deaths: {metrics['total_attr_deaths']:.0f}")
    print(f"Total YLL: {metrics['total_yll']:.0f}")
    print(f"Implied death-weighted PAF: {metrics['implied_death_weighted_paf']:.4f}")


if __name__ == "__main__":
    main()
