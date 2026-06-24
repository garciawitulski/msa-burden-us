"""Compute attributable deaths and YLL for the NHIS 2024 MSA scenario.

This script uses age-sex-specific PAFs from the NHIS 2024 current-prevalence
scenario, official all-cause deaths, and NCHS remaining life expectancy inputs.
It does not compute productivity losses, life expectancy gains, or costs.
"""

from __future__ import annotations

import re
import zlib
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXTERNAL_DIR = PROJECT_ROOT / "data/external"
TABLE_DIR = PROJECT_ROOT / "outputs/tables"
LOG_DIR = PROJECT_ROOT / "outputs/logs"

PAF_FILE = TABLE_DIR / "msa_paf_insufficient_using_nhis2024.csv"
PAF_MC_FILE = TABLE_DIR / "msa_paf_insufficient_montecarlo_using_nhis2024.csv"
DEATHS_FILE = EXTERNAL_DIR / "us_allcause_deaths_by_age_sex.csv"
LIFE_GROUP_FILE = EXTERNAL_DIR / "us_life_table_by_agegroup_sex.csv"
README = PROJECT_ROOT / "README.md"
READINESS = TABLE_DIR / "burden_readiness_report.md"
ISSUES = LOG_DIR / "issues_to_resolve.md"

DEATHS_OUT = TABLE_DIR / "msa_attributable_deaths_nhis2024.csv"
YLL_OUT = TABLE_DIR / "msa_yll_nhis2024.csv"
SUMMARY_OUT = TABLE_DIR / "msa_burden_summary_nhis2024.csv"

TARGET_PERIOD = "nhis_2024_current"
MAIN_SCENARIO = "main_strata_sex_year"
N_DRAWS = 10000
SEED = 20260429


def ensure_dirs() -> None:
    for path in [TABLE_DIR, LOG_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def append_issue_once(title: str, message: str) -> None:
    ensure_dirs()
    old = ISSUES.read_text(encoding="utf-8") if ISSUES.exists() else "# Issues to Resolve\n\n"
    if title in old:
        return
    ISSUES.write_text(old.rstrip() + f"\n\n## {datetime.now().isoformat(timespec='seconds')} - {title}\n\n{message.rstrip()}\n", encoding="utf-8")


def stop(title: str, message: str) -> None:
    append_issue_once(title, message)
    raise SystemExit(message)


def read_required(path: Path, required: list[str]) -> pd.DataFrame:
    if not path.exists():
        stop("Missing required input", f"`{path.relative_to(PROJECT_ROOT)}` was not found.")
    df = pd.read_csv(path)
    missing = [col for col in required if col not in df.columns]
    if missing:
        stop("Input missing required columns", f"`{path.relative_to(PROJECT_ROOT)}` is missing: {', '.join(missing)}.")
    return df


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    paf_required = [
        "target_period",
        "stratum",
        "age_group",
        "sex",
        "prevalence_insufficient_msa",
        "rr_scenario",
        "hazard_ratio",
        "ci_lower",
        "ci_upper",
        "paf",
    ]
    mc_required = ["target_period", "stratum", "age_group", "sex", "rr_scenario", "n_draws", "paf_median", "paf_p2_5", "paf_p97_5"]
    death_required = ["year", "sex", "age_group", "deaths_allcause", "population", "source", "notes"]
    life_required = ["year", "sex", "age_group", "remaining_life_expectancy", "source", "notes"]

    paf = read_required(PAF_FILE, paf_required)
    mc = read_required(PAF_MC_FILE, mc_required)
    deaths = read_required(DEATHS_FILE, death_required)
    life = read_required(LIFE_GROUP_FILE, life_required)

    paf = paf.loc[(paf["target_period"] == TARGET_PERIOD) & (paf["stratum"] == "age_group_sex")].copy()
    if paf.empty:
        stop("NHIS 2024 age-sex PAFs unavailable", "`msa_paf_insufficient_using_nhis2024.csv` has no `age_group_sex` rows for NHIS 2024.")
    bad = paf.loc[paf["sex"].isna() | paf["age_group"].isna()]
    if not bad.empty:
        stop("Invalid NHIS 2024 PAF strata", "Age-sex PAF rows include missing age_group or sex values.")

    deaths["deaths_allcause"] = pd.to_numeric(deaths["deaths_allcause"], errors="coerce")
    deaths["population"] = pd.to_numeric(deaths["population"], errors="coerce")
    life["remaining_life_expectancy"] = pd.to_numeric(life["remaining_life_expectancy"], errors="coerce")
    if deaths["deaths_allcause"].isna().any():
        stop("Invalid death counts", "`us_allcause_deaths_by_age_sex.csv` contains nonnumeric deaths_allcause values.")
    if life["remaining_life_expectancy"].isna().any():
        stop("Invalid life table inputs", "`us_life_table_by_agegroup_sex.csv` contains nonnumeric remaining_life_expectancy values.")

    return paf, mc, deaths, life


def choose_life_rows(life: pd.DataFrame, mortality_year: int) -> pd.DataFrame:
    rows = []
    for (age_group, sex), sub in life.groupby(["age_group", "sex"], dropna=False):
        sub = sub.copy()
        sub["distance"] = (pd.to_numeric(sub["year"], errors="coerce") - mortality_year).abs()
        chosen = sub.sort_values(["distance", "year"]).iloc[0]
        rows.append(chosen.drop(labels=["distance"]))
    return pd.DataFrame(rows)


def merge_inputs(paf: pd.DataFrame, deaths: pd.DataFrame, life: pd.DataFrame) -> pd.DataFrame:
    mortality_years = sorted(pd.to_numeric(deaths["year"], errors="coerce").dropna().astype(int).unique())
    if len(mortality_years) != 1:
        stop("Unexpected mortality years", f"Expected one mortality year, found: {mortality_years}.")
    mortality_year = mortality_years[0]
    life_use = choose_life_rows(life, mortality_year)

    deaths_use = deaths[["year", "sex", "age_group", "deaths_allcause", "population", "source", "notes"]].rename(
        columns={"year": "mortality_year", "source": "mortality_source", "notes": "mortality_notes"}
    )
    life_use = life_use[["year", "sex", "age_group", "remaining_life_expectancy", "source", "notes"]].rename(
        columns={"year": "life_table_year", "source": "life_table_source", "notes": "life_table_notes"}
    )

    merged = paf.merge(
        deaths_use,
        on=["sex", "age_group"],
        how="left",
    )
    merged = merged.merge(
        life_use,
        on=["sex", "age_group"],
        how="left",
    )
    if merged["deaths_allcause"].isna().any():
        missing = merged.loc[merged["deaths_allcause"].isna(), ["age_group", "sex"]].to_dict("records")
        stop("Missing matched death strata", f"Deaths did not match these PAF strata: {missing}.")
    if merged["remaining_life_expectancy"].isna().any():
        missing = merged.loc[merged["remaining_life_expectancy"].isna(), ["age_group", "sex"]].to_dict("records")
        stop("Missing matched life table strata", f"Life table did not match these PAF strata: {missing}.")
    return merged


def summarize_draws(values: np.ndarray) -> tuple[float, float, float]:
    return (float(np.median(values)), float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5)))


def group_key_rows(rows: pd.DataFrame) -> list[tuple[str, str, str, np.ndarray]]:
    groups: list[tuple[str, str, str, np.ndarray]] = []
    groups.append(("overall", "all", "all", rows.index.to_numpy()))
    for sex, sub in rows.groupby("sex", sort=True):
        groups.append(("sex", "all", str(sex), sub.index.to_numpy()))
    for age_group, sub in rows.groupby("age_group", sort=True):
        groups.append(("age_group", str(age_group), "all", sub.index.to_numpy()))
    for (age_group, sex), sub in rows.groupby(["age_group", "sex"], sort=True):
        groups.append(("age_group_sex", str(age_group), str(sex), sub.index.to_numpy()))
    return groups


def compute_for_scenario(rows: pd.DataFrame, scenario: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = rows.loc[rows["rr_scenario"] == scenario].copy().reset_index(drop=True)
    if rows.empty:
        stop("Missing RR scenario", f"No rows were available for rr_scenario `{scenario}`.")
    for col in ["prevalence_insufficient_msa", "hazard_ratio", "ci_lower", "ci_upper", "paf", "deaths_allcause", "remaining_life_expectancy"]:
        rows[col] = pd.to_numeric(rows[col], errors="coerce")
    if rows[["prevalence_insufficient_msa", "hazard_ratio", "ci_lower", "ci_upper", "paf"]].isna().any().any():
        stop("Invalid PAF inputs", f"PAF inputs contain missing numeric values for scenario `{scenario}`.")

    hr = float(rows["hazard_ratio"].iloc[0])
    lo = float(rows["ci_lower"].iloc[0])
    hi = float(rows["ci_upper"].iloc[0])
    se_log_hr = (np.log(hi) - np.log(lo)) / (2 * 1.96)
    rng = np.random.default_rng(SEED + zlib.crc32(scenario.encode("utf-8")) % 100000)
    hr_draws = np.exp(rng.normal(np.log(hr), se_log_hr, size=N_DRAWS))
    p = rows["prevalence_insufficient_msa"].to_numpy(dtype=float)
    paf_draws = (hr_draws[:, None] - 1.0) * p[None, :] / (1.0 + (hr_draws[:, None] - 1.0) * p[None, :])
    deaths = rows["deaths_allcause"].to_numpy(dtype=float)
    life = rows["remaining_life_expectancy"].to_numpy(dtype=float)
    death_draws = paf_draws * deaths[None, :]
    yll_draws = death_draws * life[None, :]

    rows["attributable_deaths"] = rows["paf"] * rows["deaths_allcause"]
    rows["yll"] = rows["attributable_deaths"] * rows["remaining_life_expectancy"]

    death_records = []
    yll_records = []
    summary_records = []
    for stratum, age_group, sex, idx in group_key_rows(rows):
        det_deaths = float(rows.loc[idx, "attributable_deaths"].sum())
        det_yll = float(rows.loc[idx, "yll"].sum())
        total_deaths = float(rows.loc[idx, "deaths_allcause"].sum())
        population = float(rows.loc[idx, "population"].sum()) if rows.loc[idx, "population"].notna().any() else np.nan
        death_med, death_lo, death_hi = summarize_draws(death_draws[:, idx].sum(axis=1))
        yll_med, yll_lo, yll_hi = summarize_draws(yll_draws[:, idx].sum(axis=1))
        common = {
            "rr_scenario": scenario,
            "target_period": TARGET_PERIOD,
            "stratum": stratum,
            "age_group": age_group,
            "sex": sex,
            "mortality_year": int(rows["mortality_year"].iloc[0]),
            "life_table_year": int(rows["life_table_year"].iloc[0]),
            "deaths_allcause": total_deaths,
            "population": population,
            "n_draws": N_DRAWS,
        }
        death_records.append(
            {
                **common,
                "attributable_deaths": det_deaths,
                "attributable_deaths_median": death_med,
                "attributable_deaths_p2_5": death_lo,
                "attributable_deaths_p97_5": death_hi,
                "mortality_source": rows["mortality_source"].iloc[0],
            }
        )
        yll_records.append(
            {
                **common,
                "remaining_life_expectancy": np.nan if stratum != "age_group_sex" else float(rows.loc[idx, "remaining_life_expectancy"].iloc[0]),
                "yll": det_yll,
                "yll_median": yll_med,
                "yll_p2_5": yll_lo,
                "yll_p97_5": yll_hi,
                "life_table_source": rows["life_table_source"].iloc[0],
            }
        )
        if stratum == "overall":
            summary_records.append(
                {
                    **common,
                    "hazard_ratio": hr,
                    "ci_lower": lo,
                    "ci_upper": hi,
                    "attributable_deaths": det_deaths,
                    "attributable_deaths_median": death_med,
                    "attributable_deaths_p2_5": death_lo,
                    "attributable_deaths_p97_5": death_hi,
                    "yll": det_yll,
                    "yll_median": yll_med,
                    "yll_p2_5": yll_lo,
                    "yll_p97_5": yll_hi,
                }
            )
    return pd.DataFrame(death_records), pd.DataFrame(yll_records), pd.DataFrame(summary_records)


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


def update_readiness(summary: pd.DataFrame) -> None:
    main = summary.loc[summary["rr_scenario"] == MAIN_SCENARIO]
    if main.empty:
        main = summary.iloc[[0]]
    row = main.iloc[0]
    content = f"""## NHIS 2024 Attributable Deaths and YLL

- Mortality year used: {int(row['mortality_year'])} final all-cause deaths by age group and sex.
- Life table year used: {int(row['life_table_year'])}, nearest available NCHS United States Life Tables.
- Main HR: {row['hazard_ratio']:.3f} ({row['ci_lower']:.3f}-{row['ci_upper']:.3f}).
- Total deaths potentially attributable under the modelled counterfactual: {row['attributable_deaths']:.0f}.
- Monte Carlo deaths interval: {row['attributable_deaths_p2_5']:.0f}-{row['attributable_deaths_p97_5']:.0f}.
- Total YLL potentially attributable under the modelled counterfactual: {row['yll']:.0f}.
- Monte Carlo YLL interval: {row['yll_p2_5']:.0f}-{row['yll_p97_5']:.0f}.
- Outputs: `outputs/tables/msa_attributable_deaths_nhis2024.csv`, `outputs/tables/msa_yll_nhis2024.csv`, and `outputs/tables/msa_burden_summary_nhis2024.csv`.

Interpretation remains comparative-risk and model-based. These estimates are
associated with insufficient MSA under the specified counterfactual; they should
not be interpreted as proof that insufficient MSA caused each death.
"""
    replace_marked_section(READINESS, "NHIS2024_DEATHS_YLL", content)
    text = READINESS.read_text(encoding="utf-8")
    text = text.replace("- External all-cause death counts available: no", "- External all-cause death counts available: yes")
    text = text.replace("- Life table inputs available: no", "- Life table inputs available: yes")
    READINESS.write_text(text, encoding="utf-8")


def update_readme() -> None:
    content = """## External Mortality and YLL Inputs

Run after the NHIS 2024 prevalence PAF pipeline:

```powershell
python code/python/09_download_or_prepare_external_mortality_lifetable.py
python code/python/10_compute_attributable_deaths_yll.py
```

`09_download_or_prepare_external_mortality_lifetable.py` prepares official
external inputs from CDC WONDER final all-cause mortality and NCHS United States
Life Tables. `10_compute_attributable_deaths_yll.py` links those inputs to the
NHIS 2024 age-sex PAFs and computes potentially attributable deaths and YLL.
Productivity losses, life expectancy gains, and costs are not computed here.
"""
    replace_marked_section(README, "EXTERNAL_MORTALITY_YLL", content)


def main() -> None:
    ensure_dirs()
    paf, mc, deaths, life = load_inputs()
    if mc.empty:
        stop("Missing Monte Carlo PAF summaries", "`msa_paf_insufficient_montecarlo_using_nhis2024.csv` was empty.")
    merged = merge_inputs(paf, deaths, life)
    scenarios = sorted(merged["rr_scenario"].dropna().unique())
    death_frames = []
    yll_frames = []
    summary_frames = []
    for scenario in scenarios:
        deaths_s, yll_s, summary_s = compute_for_scenario(merged, scenario)
        death_frames.append(deaths_s)
        yll_frames.append(yll_s)
        summary_frames.append(summary_s)

    death_out = pd.concat(death_frames, ignore_index=True)
    yll_out = pd.concat(yll_frames, ignore_index=True)
    summary_out = pd.concat(summary_frames, ignore_index=True)
    death_out.to_csv(DEATHS_OUT, index=False)
    yll_out.to_csv(YLL_OUT, index=False)
    summary_out.to_csv(SUMMARY_OUT, index=False)
    update_readiness(summary_out)
    update_readme()

    if int(summary_out["mortality_year"].iloc[0]) != int(summary_out["life_table_year"].iloc[0]):
        append_issue_once(
            "Mortality and YLL life-table year mismatch",
            f"Attributable deaths use {int(summary_out['mortality_year'].iloc[0])} final mortality, while YLL uses {int(summary_out['life_table_year'].iloc[0])} NCHS remaining life expectancy because a matching life table was not available in the prepared inputs.",
        )

    main = summary_out.loc[summary_out["rr_scenario"] == MAIN_SCENARIO]
    if not main.empty:
        row = main.iloc[0]
        print(f"Created: {DEATHS_OUT.relative_to(PROJECT_ROOT)}")
        print(f"Created: {YLL_OUT.relative_to(PROJECT_ROOT)}")
        print(f"Created: {SUMMARY_OUT.relative_to(PROJECT_ROOT)}")
        print(f"Main attributable deaths: {row['attributable_deaths']:.0f}")
        print(f"Main YLL: {row['yll']:.0f}")


if __name__ == "__main__":
    main()
