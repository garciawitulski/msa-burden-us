"""Estimate modelled life expectancy gains for the NHIS 2024 MSA scenario.

This script adds a life-table module after the validated mortality/YLL burden
pipeline. It does not rerun Cox models and does not alter existing burden
outputs. The counterfactual mortality schedule is:

    counterfactual_mx = observed_mx * (1 - PAF_age_sex)

for adult ages covered by the insufficient-MSA burden analysis. Ages below 18
receive PAF = 0. Current prepared mortality inputs are adult broad age groups,
so the primary estimate is an approximate adult abridged life-table result.
For life expectancy at birth, a hybrid table uses NCHS 2023 annual qx below age
18 and CDC WONDER 2024 adult broad-group mx at age 18+.
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
DOCS_DIR = PROJECT_ROOT / "docs"
LOG_DIR = PROJECT_ROOT / "outputs/logs"

DEATHS_FILE = EXTERNAL_DIR / "us_allcause_deaths_by_age_sex.csv"
PAF_FILE = TABLE_DIR / "msa_paf_insufficient_using_nhis2024.csv"
DEATHS_PREMATURE_FILE = EXTERNAL_DIR / "us_allcause_deaths_by_age_sex_premature_30_69.csv"
PAF_PREMATURE_FILE = TABLE_DIR / "msa_paf_insufficient_premature_30_69_nhis2024.csv"
LIFE_TABLE_MALE_XLSX = EXTERNAL_DIR / "nchs_life_tables_2023/Table02.xlsx"
LIFE_TABLE_FEMALE_XLSX = EXTERNAL_DIR / "nchs_life_tables_2023/Table03.xlsx"

OUT_GAIN = TABLE_DIR / "msa_life_expectancy_gain_nhis2024.csv"
OUT_MC = TABLE_DIR / "msa_life_expectancy_gain_montecarlo_nhis2024.csv"
OUT_TABLE = TABLE_DIR / "msa_life_table_observed_counterfactual_nhis2024.csv"
OUT_REPORT = TABLE_DIR / "msa_life_expectancy_gain_report.md"
OUT_GAIN_PREMATURE = TABLE_DIR / "msa_life_expectancy_gain_premature_30_69_nhis2024.csv"
OUT_MC_PREMATURE = TABLE_DIR / "msa_life_expectancy_gain_montecarlo_premature_30_69_nhis2024.csv"
OUT_TABLE_PREMATURE = TABLE_DIR / "msa_life_table_observed_counterfactual_premature_30_69_nhis2024.csv"
OUT_REPORT_PREMATURE = TABLE_DIR / "msa_life_expectancy_gain_report_premature_30_69.md"
DOC_NEEDED = DOCS_DIR / "external_life_expectancy_gain_data_needed.md"
ISSUES = LOG_DIR / "issues_to_resolve.md"

PRIMARY_SCENARIO = "main_strata_sex_year"
PRIMARY_PREMATURE_SCENARIO = "main_hr_target_30_69"
AGE_ORDER = ["18-34", "35-44", "45-54", "55-64", "65-74", "75+"]
SEX_ORDER = ["Female", "Male"]
AGE_START = {"18-34": 18, "35-44": 35, "45-54": 45, "55-64": 55, "65-74": 65, "75+": 75}
AGE_END = {"18-34": 35, "35-44": 45, "45-54": 55, "55-64": 65, "65-74": 75, "75+": math.inf}
AGE_WIDTH = {"18-34": 17.0, "35-44": 10.0, "45-54": 10.0, "55-64": 10.0, "65-74": 10.0, "75+": math.inf}
SEED = 20260429
N_DRAWS = 10_000
P_AGE_ORDER = ["30-34", "35-44", "45-54", "55-64", "65-69"]
P_AGE_START = {"30-34": 30, "35-44": 35, "45-54": 45, "55-64": 55, "65-69": 65}
P_AGE_END = {"30-34": 35, "35-44": 45, "45-54": 55, "55-64": 65, "65-69": 70}
P_AGE_WIDTH = {"30-34": 5.0, "35-44": 10.0, "45-54": 10.0, "55-64": 10.0, "65-69": 5.0}


def ensure_dirs() -> None:
    for path in [TABLE_DIR, DOCS_DIR, LOG_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def append_issue_once(title: str, message: str) -> None:
    ensure_dirs()
    old = ISSUES.read_text(encoding="utf-8") if ISSUES.exists() else "# Issues to Resolve\n\n"
    if title in old:
        return
    stamp = datetime.now().isoformat(timespec="seconds")
    ISSUES.write_text(old.rstrip() + f"\n\n## {stamp} - {title}\n\n{message.rstrip()}\n", encoding="utf-8")


def stop(title: str, message: str) -> None:
    append_issue_once(title, message)
    raise SystemExit(message)


def read_required(path: Path, required: list[str] | None = None) -> pd.DataFrame:
    if not path.exists():
        stop("Missing life expectancy gain input", f"Required input is missing: `{path.relative_to(PROJECT_ROOT)}`.")
    df = pd.read_csv(path)
    if required:
        missing = [col for col in required if col not in df.columns]
        if missing:
            stop(
                "Malformed life expectancy gain input",
                f"`{path.relative_to(PROJECT_ROOT)}` is missing required columns: {', '.join(missing)}.",
            )
    return df


def write_fine_age_doc() -> None:
    text = """# External Data Needed For Finer Life Expectancy Gain Estimates

The current life expectancy gain module can run with the validated broad adult
CDC WONDER mortality file:

- `data/external/us_allcause_deaths_by_age_sex.csv`

That file has age groups 18-34, 35-44, 45-54, 55-64, 65-74, and 75+. Therefore,
life expectancy gains are approximate abridged life-table estimates.

For a finer life-table estimate, manually export official CDC WONDER final
all-cause mortality for the latest final mortality year used in the burden
analysis, currently 2024:

1. Data source: CDC WONDER Underlying Cause of Death, 2018-2024, Single Race.
2. Geography: United States.
3. Year: 2024 final mortality.
4. Cause of death: All causes.
5. Group results by sex and fine age group.
6. Export deaths and population for: <1, 1-4, 5-9, 10-14, 15-17, 18-19,
   20-24, 25-29, 30-34, 35-39, 40-44, 45-49, 50-54, 55-59, 60-64, 65-69,
   70-74, 75-79, 80-84, and 85+.
7. Save the prepared file as
   `data/external/us_allcause_deaths_by_fine_age_sex.csv` with columns:
   `year`, `sex`, `age_group`, `age_start`, `age_end`, `deaths_allcause`,
   `population`, `source`, and `notes`.

Do not enter hand-estimated death counts or populations. Use official exported
CDC/NCHS values only.
"""
    DOC_NEEDED.write_text(text, encoding="utf-8")


def age_label_to_start(label: object) -> int | None:
    text = str(label)
    match = re.match(r"^\s*(\d+)", text)
    if match:
        return int(match.group(1))
    return None


def load_nchs_child_intervals(sex: str) -> list[dict[str, float | str]]:
    path = LIFE_TABLE_FEMALE_XLSX if sex == "Female" else LIFE_TABLE_MALE_XLSX
    if not path.exists():
        stop("Missing NCHS life table workbook", f"Missing `{path.relative_to(PROJECT_ROOT)}`.")
    raw = pd.read_excel(path, header=[1, 2])
    raw.columns = ["age_label", "qx", "lx", "dx", "Lx", "Tx", "ex"]
    raw["age_start"] = raw["age_label"].map(age_label_to_start)
    raw = raw.loc[raw["age_start"].between(0, 17, inclusive="both")].copy()
    raw = raw.dropna(subset=["qx", "lx", "dx", "Lx"])
    intervals: list[dict[str, float | str]] = []
    for _, row in raw.iterrows():
        qx = float(row["qx"])
        lx = float(row["lx"])
        dx = float(row["dx"])
        lx_next = lx - dx
        ax = float((float(row["Lx"]) - lx_next) / dx) if dx > 0 else 0.5
        intervals.append(
            {
                "sex": sex,
                "age_group": f"{int(row['age_start'])}",
                "age_start": float(row["age_start"]),
                "age_end": float(row["age_start"] + 1),
                "interval_width": 1.0,
                "mx": np.nan,
                "qx": qx,
                "ax": ax,
                "paf": 0.0,
                "source": "NCHS United States Life Tables 2023",
            }
        )
    return intervals


def qx_from_mx(mx: float, n: float, ax: float) -> float:
    if not np.isfinite(mx) or mx < 0:
        return np.nan
    if not np.isfinite(n):
        return 1.0
    qx = (n * mx) / (1.0 + (n - ax) * mx)
    return float(min(max(qx, 0.0), 1.0))


def adult_intervals(
    deaths: pd.DataFrame,
    pafs: dict[tuple[str, str], float],
    sex: str,
    counterfactual: bool,
) -> list[dict[str, float | str]]:
    if sex == "All":
        grouped = deaths.groupby("age_group", as_index=False)[["deaths_allcause", "population"]].sum()
    else:
        grouped = deaths.loc[deaths["sex"] == sex].copy()
    intervals: list[dict[str, float | str]] = []
    for age_group in AGE_ORDER:
        match = grouped.loc[grouped["age_group"] == age_group]
        if match.empty:
            stop("Missing adult mortality stratum", f"Missing mortality row for sex={sex}, age_group={age_group}.")
        row = match.iloc[0]
        observed_mx = float(row["deaths_allcause"]) / float(row["population"])
        paf = float(pafs.get((sex, age_group), 0.0))
        mx = observed_mx * (1.0 - paf) if counterfactual else observed_mx
        n = AGE_WIDTH[age_group]
        ax = (n / 2.0) if np.isfinite(n) else (1.0 / mx if mx > 0 else 0.0)
        intervals.append(
            {
                "sex": sex,
                "age_group": age_group,
                "age_start": float(AGE_START[age_group]),
                "age_end": float(AGE_END[age_group]) if np.isfinite(AGE_END[age_group]) else np.nan,
                "interval_width": n,
                "mx": mx,
                "observed_mx": observed_mx,
                "qx": qx_from_mx(mx, n, ax),
                "ax": ax,
                "paf": paf,
                "source": "CDC WONDER 2024 final all-cause mortality",
            }
        )
    return intervals


def build_life_table(intervals: list[dict[str, float | str]], radix: float = 100_000.0) -> pd.DataFrame:
    rows: list[dict[str, float | str]] = []
    lx = radix
    for item in intervals:
        n = float(item["interval_width"])
        mx = float(item["mx"]) if pd.notna(item.get("mx", np.nan)) else np.nan
        qx = float(item["qx"])
        qx = min(max(qx, 0.0), 1.0)
        dx = lx * qx
        if np.isfinite(n):
            ax = float(item["ax"])
            lx_next = lx - dx
            Lx = n * lx_next + ax * dx
        else:
            Lx = lx / mx if mx and mx > 0 else np.nan
        row = dict(item)
        row.update({"lx": lx, "dx": dx, "Lx": Lx})
        rows.append(row)
        lx = max(lx - dx, 0.0)

    df = pd.DataFrame(rows)
    df["Tx"] = df["Lx"][::-1].cumsum()[::-1]
    df["ex"] = df["Tx"] / df["lx"].replace(0, np.nan)
    return df


def lookup_ex(table: pd.DataFrame, start_age: int) -> float:
    match = table.loc[np.isclose(table["age_start"], float(start_age))]
    if match.empty:
        return np.nan
    return float(match.iloc[0]["ex"])


def make_paf_maps(paf: pd.DataFrame) -> tuple[dict[tuple[str, str], float], dict[tuple[str, str], float]]:
    paf = paf.copy()
    paf["paf"] = pd.to_numeric(paf["paf"], errors="coerce")
    age_sex = paf.loc[(paf["rr_scenario"] == PRIMARY_SCENARIO) & (paf["stratum"] == "age_group_sex")]
    age_all = paf.loc[(paf["rr_scenario"] == PRIMARY_SCENARIO) & (paf["stratum"] == "age_group")]
    sex_map = {(str(r["sex"]), str(r["age_group"])): float(r["paf"]) for _, r in age_sex.iterrows()}
    all_map = {("All", str(r["age_group"])): float(r["paf"]) for _, r in age_all.iterrows()}
    return sex_map, all_map


def make_paf_draw_maps(paf: pd.DataFrame, n_draws: int = N_DRAWS) -> list[dict[tuple[str, str], float]]:
    age_sex = paf.loc[(paf["rr_scenario"] == PRIMARY_SCENARIO) & (paf["stratum"] == "age_group_sex")].copy()
    age_all = paf.loc[(paf["rr_scenario"] == PRIMARY_SCENARIO) & (paf["stratum"] == "age_group")].copy()
    required = ["hazard_ratio", "ci_lower", "ci_upper", "prevalence_insufficient_msa"]
    if any(col not in age_sex.columns for col in required):
        stop("Missing PAF uncertainty inputs", "PAF file lacks HR CI or prevalence columns needed for Monte Carlo life tables.")
    hr = float(age_sex["hazard_ratio"].dropna().iloc[0])
    lo = float(age_sex["ci_lower"].dropna().iloc[0])
    hi = float(age_sex["ci_upper"].dropna().iloc[0])
    se_log_hr = (math.log(hi) - math.log(lo)) / (2.0 * 1.96)
    rng = np.random.default_rng(SEED)
    hr_draws = np.exp(rng.normal(math.log(hr), se_log_hr, size=n_draws))

    strata = pd.concat([age_sex, age_all], ignore_index=True)
    strata["map_sex"] = np.where(strata["stratum"] == "age_group", "All", strata["sex"].astype(str))
    strata["prevalence_insufficient_msa"] = pd.to_numeric(strata["prevalence_insufficient_msa"], errors="coerce")
    draw_maps: list[dict[tuple[str, str], float]] = []
    for hr_sim in hr_draws:
        this: dict[tuple[str, str], float] = {}
        for _, row in strata.iterrows():
            p = float(row["prevalence_insufficient_msa"])
            paf_sim = p * (hr_sim - 1.0) / (p * (hr_sim - 1.0) + 1.0)
            this[(str(row["map_sex"]), str(row["age_group"]))] = float(paf_sim)
        draw_maps.append(this)
    return draw_maps


def life_expectancy_rows(deaths: pd.DataFrame, sex_pafs: dict[tuple[str, str], float], all_pafs: dict[tuple[str, str], float]) -> tuple[pd.DataFrame, pd.DataFrame]:
    gain_rows: list[dict[str, object]] = []
    table_rows: list[pd.DataFrame] = []

    for sex in SEX_ORDER:
        observed = build_life_table(load_nchs_child_intervals(sex) + adult_intervals(deaths, sex_pafs, sex, counterfactual=False))
        counter = build_life_table(load_nchs_child_intervals(sex) + adult_intervals(deaths, sex_pafs, sex, counterfactual=True))
        for scenario, table in [("observed", observed), ("counterfactual", counter)]:
            table = table.copy()
            table["scenario"] = scenario
            table["estimate_type"] = "hybrid approximate e0/e18 using NCHS 2023 child qx and CDC WONDER 2024 adult broad mx"
            table_rows.append(table)
        for start_age in [0, 18, 65]:
            obs = lookup_ex(observed, start_age)
            ctf = lookup_ex(counter, start_age)
            gain_rows.append(
                {
                    "sex": sex,
                    "life_expectancy_start_age": start_age,
                    "observed_life_expectancy": obs,
                    "counterfactual_life_expectancy": ctf,
                    "gain_years": ctf - obs,
                    "estimate_type": "hybrid_approximate" if start_age == 0 else "adult_broad_abridged",
                    "mortality_year": 2024,
                    "life_table_child_year": 2023,
                    "paf_scenario": PRIMARY_SCENARIO,
                }
            )

    for sex in ["All"]:
        observed = build_life_table(adult_intervals(deaths, all_pafs, sex, counterfactual=False))
        counter = build_life_table(adult_intervals(deaths, all_pafs, sex, counterfactual=True))
        for scenario, table in [("observed", observed), ("counterfactual", counter)]:
            table = table.copy()
            table["scenario"] = scenario
            table["estimate_type"] = "adult broad abridged table from age 18"
            table_rows.append(table)
        for start_age in [18, 65]:
            obs = lookup_ex(observed, start_age)
            ctf = lookup_ex(counter, start_age)
            gain_rows.append(
                {
                    "sex": sex,
                    "life_expectancy_start_age": start_age,
                    "observed_life_expectancy": obs,
                    "counterfactual_life_expectancy": ctf,
                    "gain_years": ctf - obs,
                    "estimate_type": "adult_broad_abridged",
                    "mortality_year": 2024,
                    "life_table_child_year": np.nan,
                    "paf_scenario": PRIMARY_SCENARIO,
                }
            )

    return pd.DataFrame(gain_rows), pd.concat(table_rows, ignore_index=True)


def monte_carlo_gains(deaths: pd.DataFrame, draw_maps: list[dict[tuple[str, str], float]]) -> pd.DataFrame:
    collector: dict[tuple[str, int, str], list[float]] = {}
    child_intervals = {sex: load_nchs_child_intervals(sex) for sex in SEX_ORDER}
    observed_by_sex = {
        sex: build_life_table(child_intervals[sex] + adult_intervals(deaths, {}, sex, counterfactual=False))
        for sex in SEX_ORDER
    }
    observed_all = build_life_table(adult_intervals(deaths, {}, "All", counterfactual=False))
    for paf_map in draw_maps:
        for sex in SEX_ORDER:
            observed = observed_by_sex[sex]
            counter = build_life_table(child_intervals[sex] + adult_intervals(deaths, paf_map, sex, counterfactual=True))
            for start_age in [0, 18, 65]:
                collector.setdefault((sex, start_age, "hybrid_approximate" if start_age == 0 else "adult_broad_abridged"), []).append(
                    lookup_ex(counter, start_age) - lookup_ex(observed, start_age)
                )
        counter_all = build_life_table(adult_intervals(deaths, paf_map, "All", counterfactual=True))
        for start_age in [18, 65]:
            collector.setdefault(("All", start_age, "adult_broad_abridged"), []).append(
                lookup_ex(counter_all, start_age) - lookup_ex(observed_all, start_age)
            )

    rows = []
    for (sex, start_age, estimate_type), draws in collector.items():
        arr = np.asarray(draws, dtype=float)
        rows.append(
            {
                "sex": sex,
                "life_expectancy_start_age": start_age,
                "estimate_type": estimate_type,
                "n_draws": len(arr),
                "gain_years_median": np.nanmedian(arr),
                "gain_years_p2_5": np.nanpercentile(arr, 2.5),
                "gain_years_p97_5": np.nanpercentile(arr, 97.5),
            }
        )
    return pd.DataFrame(rows)


def write_report(gain: pd.DataFrame, mc: pd.DataFrame) -> None:
    main = gain.loc[(gain["sex"] == "All") & (gain["life_expectancy_start_age"] == 18)].iloc[0]
    main_mc = mc.loc[(mc["sex"] == "All") & (mc["life_expectancy_start_age"] == 18)].iloc[0]
    female_birth = gain.loc[(gain["sex"] == "Female") & (gain["life_expectancy_start_age"] == 0)].iloc[0]
    male_birth = gain.loc[(gain["sex"] == "Male") & (gain["life_expectancy_start_age"] == 0)].iloc[0]
    text = f"""# Life Expectancy Gain Report

Generated: {datetime.now().isoformat(timespec="seconds")}

## Inputs

- Mortality rates: CDC WONDER final 2024 all-cause deaths and population from `data/external/us_allcause_deaths_by_age_sex.csv`.
- PAFs: NHIS 2024 age-sex-specific PAFs using the refined insufficient-MSA HR from `outputs/tables/msa_paf_insufficient_using_nhis2024.csv`.
- Below-age-18 mortality schedule for e0: NCHS United States Life Tables 2023, with PAF set to 0 below age 18.

## Method

The counterfactual schedule applies `counterfactual_mx = observed_mx * (1 - PAF_age_sex)` for adults.
Because the current official mortality input is available in broad adult age groups
(18-34, 35-44, 45-54, 55-64, 65-74, 75+), the estimates are approximate abridged
life-table estimates. Life expectancy at birth is a hybrid estimate that combines
NCHS 2023 annual qx below age 18 with CDC WONDER 2024 broad adult mortality rates.

Monte Carlo uncertainty was reconstructed from the refined HR confidence interval
and the fixed NHIS 2024 stratum-specific prevalence, using {N_DRAWS:,} draws.

## Main Estimates

- Approximate adult life expectancy at age 18, total population: observed {main['observed_life_expectancy']:.2f} years, counterfactual {main['counterfactual_life_expectancy']:.2f} years, gain {main['gain_years']:.3f} years.
- Monte Carlo interval for the age-18 gain, total population: {main_mc['gain_years_median']:.3f} years ({main_mc['gain_years_p2_5']:.3f} to {main_mc['gain_years_p97_5']:.3f}).
- Hybrid life expectancy at birth gain: Female {female_birth['gain_years']:.3f} years; Male {male_birth['gain_years']:.3f} years.

## Limitations

- PAFs are based on observational HRs and should be interpreted as modelled counterfactual estimates.
- PAFs are available at the NHIS 2024 age-sex group resolution, not single-year age resolution.
- Broad adult age groups make life expectancy gains approximate; finer CDC WONDER age groups would improve this module.
- NHIS 2024 prevalence is cross-sectional and is used only for contemporary exposure prevalence.
- The estimates should be described as life expectancy gains under the modelled counterfactual of meeting MSA guidelines, not as gains caused by MSA.
"""
    OUT_REPORT.write_text(text, encoding="utf-8")


def premature_paf_maps(paf: pd.DataFrame) -> tuple[dict[tuple[str, str], float], dict[tuple[str, str], float]]:
    paf = paf.copy()
    paf["paf"] = pd.to_numeric(paf["paf"], errors="coerce")
    age_sex = paf.loc[(paf["rr_scenario"] == PRIMARY_PREMATURE_SCENARIO) & (paf["stratum"] == "age_group_sex")]
    age_all = paf.loc[(paf["rr_scenario"] == PRIMARY_PREMATURE_SCENARIO) & (paf["stratum"] == "age_group")]
    return (
        {(str(r["sex"]), str(r["age_group"])): float(r["paf"]) for _, r in age_sex.iterrows()},
        {("All", str(r["age_group"])): float(r["paf"]) for _, r in age_all.iterrows()},
    )


def premature_paf_draw_maps(paf: pd.DataFrame) -> list[dict[tuple[str, str], float]]:
    age_sex = paf.loc[(paf["rr_scenario"] == PRIMARY_PREMATURE_SCENARIO) & (paf["stratum"] == "age_group_sex")].copy()
    age_all = paf.loc[(paf["rr_scenario"] == PRIMARY_PREMATURE_SCENARIO) & (paf["stratum"] == "age_group")].copy()
    hr = float(age_sex["hazard_ratio"].dropna().iloc[0])
    lo = float(age_sex["ci_lower"].dropna().iloc[0])
    hi = float(age_sex["ci_upper"].dropna().iloc[0])
    se_log_hr = (math.log(hi) - math.log(lo)) / (2.0 * 1.96)
    rng = np.random.default_rng(SEED)
    hr_draws = np.exp(rng.normal(math.log(hr), se_log_hr, size=N_DRAWS))
    strata = pd.concat([age_sex, age_all], ignore_index=True)
    strata["map_sex"] = np.where(strata["stratum"] == "age_group", "All", strata["sex"].astype(str))
    strata["prevalence_insufficient_msa"] = pd.to_numeric(strata["prevalence_insufficient_msa"], errors="coerce")
    draw_maps = []
    for hr_sim in hr_draws:
        this = {}
        for _, row in strata.iterrows():
            p = float(row["prevalence_insufficient_msa"])
            this[(str(row["map_sex"]), str(row["age_group"]))] = float(p * (hr_sim - 1.0) / (p * (hr_sim - 1.0) + 1.0))
        draw_maps.append(this)
    return draw_maps


def premature_intervals(deaths: pd.DataFrame, pafs: dict[tuple[str, str], float], sex: str, counterfactual: bool) -> list[dict[str, float | str]]:
    if sex == "All":
        grouped = deaths.groupby("age_group", as_index=False)[["deaths_allcause", "population"]].sum()
    else:
        grouped = deaths.loc[deaths["sex"] == sex].copy()
    intervals = []
    for age_group in P_AGE_ORDER:
        match = grouped.loc[grouped["age_group"] == age_group]
        if match.empty:
            stop("Missing premature mortality stratum for life table", f"Missing {sex} / {age_group}.")
        row = match.iloc[0]
        observed_mx = float(row["deaths_allcause"]) / float(row["population"])
        paf = float(pafs.get((sex, age_group), 0.0))
        mx = observed_mx * (1.0 - paf) if counterfactual else observed_mx
        n = P_AGE_WIDTH[age_group]
        ax = n / 2.0
        intervals.append(
            {
                "sex": sex,
                "age_group": age_group,
                "age_start": float(P_AGE_START[age_group]),
                "age_end": float(P_AGE_END[age_group]),
                "interval_width": n,
                "observed_mx": observed_mx,
                "mx": mx,
                "qx": qx_from_mx(mx, n, ax),
                "ax": ax,
                "paf": paf,
                "source": "CDC WONDER 2024 final all-cause mortality, ages 30-69",
            }
        )
    return intervals


def build_temporary_table(intervals: list[dict[str, float | str]], radix: float = 100_000.0) -> pd.DataFrame:
    rows = []
    lx = radix
    for item in intervals:
        n = float(item["interval_width"])
        qx = min(max(float(item["qx"]), 0.0), 1.0)
        dx = lx * qx
        lx_next = lx - dx
        Lx = n * lx_next + float(item["ax"]) * dx
        row = dict(item)
        row.update({"lx": lx, "dx": dx, "Lx": Lx, "lx_next": lx_next})
        rows.append(row)
        lx = max(lx_next, 0.0)
    return pd.DataFrame(rows)


def temporary_metrics(table: pd.DataFrame) -> dict[str, float]:
    radix = float(table["lx"].iloc[0])
    l70 = float(table["lx_next"].iloc[-1])
    return {
        "probability_death_30_70": 1.0 - l70 / radix,
        "probability_survival_30_70": l70 / radix,
        "temporary_life_expectancy_30_70": float(table["Lx"].sum() / radix),
    }


def premature_life_expectancy_outputs(deaths: pd.DataFrame, paf: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    sex_pafs, all_pafs = premature_paf_maps(paf)
    gain_rows = []
    table_rows = []
    for sex, pafs in [("Female", sex_pafs), ("Male", sex_pafs), ("All", all_pafs)]:
        observed = build_temporary_table(premature_intervals(deaths, pafs, sex, counterfactual=False))
        counter = build_temporary_table(premature_intervals(deaths, pafs, sex, counterfactual=True))
        observed_metrics = temporary_metrics(observed)
        counter_metrics = temporary_metrics(counter)
        for scenario, table in [("observed", observed), ("counterfactual", counter)]:
            table = table.copy()
            table["scenario"] = scenario
            table["estimate_type"] = "temporary_life_table_30_70_broad_age_groups"
            table_rows.append(table)
        gain_rows.append(
            {
                "sex": sex,
                "observed_probability_death_30_70": observed_metrics["probability_death_30_70"],
                "counterfactual_probability_death_30_70": counter_metrics["probability_death_30_70"],
                "absolute_reduction_probability_death_30_70": observed_metrics["probability_death_30_70"] - counter_metrics["probability_death_30_70"],
                "observed_probability_survival_30_70": observed_metrics["probability_survival_30_70"],
                "counterfactual_probability_survival_30_70": counter_metrics["probability_survival_30_70"],
                "observed_temporary_life_expectancy_30_70": observed_metrics["temporary_life_expectancy_30_70"],
                "counterfactual_temporary_life_expectancy_30_70": counter_metrics["temporary_life_expectancy_30_70"],
                "gain_temporary_life_expectancy_30_70": counter_metrics["temporary_life_expectancy_30_70"] - observed_metrics["temporary_life_expectancy_30_70"],
                "estimate_type": "temporary_life_table_30_70_broad_age_groups",
                "mortality_year": 2024,
                "paf_scenario": PRIMARY_PREMATURE_SCENARIO,
            }
        )
    gain = pd.DataFrame(gain_rows)
    table = pd.concat(table_rows, ignore_index=True)

    observed_tables = {
        sex: build_temporary_table(premature_intervals(deaths, {}, sex, counterfactual=False))
        for sex in ["Female", "Male", "All"]
    }
    collector: dict[str, dict[str, list[float]]] = {
        sex: {"gain": [], "death_reduction": [], "survival_gain": []} for sex in ["Female", "Male", "All"]
    }
    for draw_map in premature_paf_draw_maps(paf):
        for sex in ["Female", "Male", "All"]:
            observed_metrics = temporary_metrics(observed_tables[sex])
            counter = build_temporary_table(premature_intervals(deaths, draw_map, sex, counterfactual=True))
            counter_metrics = temporary_metrics(counter)
            collector[sex]["gain"].append(counter_metrics["temporary_life_expectancy_30_70"] - observed_metrics["temporary_life_expectancy_30_70"])
            collector[sex]["death_reduction"].append(observed_metrics["probability_death_30_70"] - counter_metrics["probability_death_30_70"])
            collector[sex]["survival_gain"].append(counter_metrics["probability_survival_30_70"] - observed_metrics["probability_survival_30_70"])
    mc_rows = []
    for sex, values in collector.items():
        gain_arr = np.asarray(values["gain"])
        death_arr = np.asarray(values["death_reduction"])
        surv_arr = np.asarray(values["survival_gain"])
        mc_rows.append(
            {
                "sex": sex,
                "n_draws": N_DRAWS,
                "gain_temporary_life_expectancy_30_70_median": np.nanmedian(gain_arr),
                "gain_temporary_life_expectancy_30_70_p2_5": np.nanpercentile(gain_arr, 2.5),
                "gain_temporary_life_expectancy_30_70_p97_5": np.nanpercentile(gain_arr, 97.5),
                "absolute_reduction_probability_death_30_70_median": np.nanmedian(death_arr),
                "absolute_reduction_probability_death_30_70_p2_5": np.nanpercentile(death_arr, 2.5),
                "absolute_reduction_probability_death_30_70_p97_5": np.nanpercentile(death_arr, 97.5),
                "absolute_gain_probability_survival_30_70_median": np.nanmedian(surv_arr),
                "absolute_gain_probability_survival_30_70_p2_5": np.nanpercentile(surv_arr, 2.5),
                "absolute_gain_probability_survival_30_70_p97_5": np.nanpercentile(surv_arr, 97.5),
            }
        )
    return gain, pd.DataFrame(mc_rows), table


def write_premature_report(gain: pd.DataFrame, mc: pd.DataFrame) -> None:
    main = gain.loc[gain["sex"] == "All"].iloc[0]
    main_mc = mc.loc[mc["sex"] == "All"].iloc[0]
    text = f"""# Premature 30-69 Life Expectancy Gain Report

Generated: {datetime.now().isoformat(timespec="seconds")}

## Inputs

- Mortality rates: CDC WONDER final 2024 all-cause deaths and population for ages 30-69.
- PAFs: NHIS 2024 age-sex-specific premature 30-69 PAFs using the reviewer-response target-population HR.
- Age groups: 30-34, 35-44, 45-54, 55-64, and 65-69.

## Method

The main metric is temporary life expectancy from age 30 to age 70. The
counterfactual schedule applies `counterfactual_mx = observed_mx * (1 - PAF)`
within each age-sex stratum. Because mortality inputs are grouped, estimates are
approximate broad-group temporary life-table estimates.

## Main Estimates

- Observed probability of death from age 30 to 70, total population: {main['observed_probability_death_30_70']:.4f}.
- Counterfactual probability of death from age 30 to 70: {main['counterfactual_probability_death_30_70']:.4f}.
- Temporary life expectancy 30-70: observed {main['observed_temporary_life_expectancy_30_70']:.3f} years; counterfactual {main['counterfactual_temporary_life_expectancy_30_70']:.3f} years.
- Gain in temporary life expectancy 30-70: {main['gain_temporary_life_expectancy_30_70']:.3f} years.
- Monte Carlo interval for the temporary life expectancy gain: {main_mc['gain_temporary_life_expectancy_30_70_p2_5']:.3f} to {main_mc['gain_temporary_life_expectancy_30_70_p97_5']:.3f} years.

## Limitations

- The HR is the reviewer-response target-population Cox estimate for baseline adults aged 30-69, censored at age 70.
- PAFs are based on observational HRs and should be interpreted as modelled counterfactual estimates.
- Broad age groups make temporary life-table gains approximate.
- NHIS 2024 prevalence is cross-sectional and is used only for contemporary exposure prevalence.
"""
    OUT_REPORT_PREMATURE.write_text(text, encoding="utf-8")


def main() -> None:
    ensure_dirs()
    write_fine_age_doc()
    deaths = read_required(DEATHS_FILE, ["year", "sex", "age_group", "deaths_allcause", "population"])
    paf = read_required(PAF_FILE, ["rr_scenario", "stratum", "age_group", "sex", "paf"])
    deaths["deaths_allcause"] = pd.to_numeric(deaths["deaths_allcause"], errors="coerce")
    deaths["population"] = pd.to_numeric(deaths["population"], errors="coerce")
    if deaths[["deaths_allcause", "population"]].isna().any().any() or (deaths["population"] <= 0).any():
        stop("Invalid mortality rates for life expectancy gain", "Death counts and population must be numeric and population must be positive.")

    sex_pafs, all_pafs = make_paf_maps(paf)
    gain, observed_counterfactual = life_expectancy_rows(deaths, sex_pafs, all_pafs)
    draw_maps = make_paf_draw_maps(paf)
    mc = monte_carlo_gains(deaths, draw_maps)

    gain.to_csv(OUT_GAIN, index=False)
    mc.to_csv(OUT_MC, index=False)
    observed_counterfactual.to_csv(OUT_TABLE, index=False)
    write_report(gain, mc)

    premature_deaths = read_required(DEATHS_PREMATURE_FILE, ["year", "sex", "age_group", "deaths_allcause", "population"])
    premature_paf = read_required(PAF_PREMATURE_FILE, ["rr_scenario", "stratum", "age_group", "sex", "paf"])
    premature_deaths["deaths_allcause"] = pd.to_numeric(premature_deaths["deaths_allcause"], errors="coerce")
    premature_deaths["population"] = pd.to_numeric(premature_deaths["population"], errors="coerce")
    premature_gain, premature_mc, premature_table = premature_life_expectancy_outputs(premature_deaths, premature_paf)
    premature_gain.to_csv(OUT_GAIN_PREMATURE, index=False)
    premature_mc.to_csv(OUT_MC_PREMATURE, index=False)
    premature_table.to_csv(OUT_TABLE_PREMATURE, index=False)
    write_premature_report(premature_gain, premature_mc)

    append_issue_once(
        "Life expectancy gain uses broad adult age groups",
        "The life expectancy gain module ran with official CDC WONDER 2024 adult mortality in broad age groups. Outputs are approximate abridged or hybrid life-table estimates. Finer age-specific mortality instructions were written to `docs/external_life_expectancy_gain_data_needed.md`.",
    )
    append_issue_once(
        "Premature 30-69 temporary life expectancy uses broad age groups",
        "The premature 30-69 life expectancy module ran with official CDC WONDER 2024 mortality in age groups 30-34, 35-44, 45-54, 55-64, and 65-69. Temporary life expectancy 30-70 estimates are approximate broad-group life-table estimates.",
    )
    print(f"Wrote {OUT_GAIN.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {OUT_MC.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {OUT_TABLE.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {OUT_REPORT.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {OUT_GAIN_PREMATURE.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {OUT_MC_PREMATURE.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {OUT_TABLE_PREMATURE.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {OUT_REPORT_PREMATURE.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
