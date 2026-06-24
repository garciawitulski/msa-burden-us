"""Compute premature mortality deaths and YLL for ages 30-69.

This script creates a WHO-style premature mortality burden module while keeping
the previous all-adult 18+ outputs intact. It uses the reviewer-response
target-population HR for insufficient MSA among baseline adults aged 30-69
censored at age 70, NHIS 2024 age-sex-specific prevalence for ages 30-69, and
official CDC WONDER final 2024 all-cause mortality.
"""

from __future__ import annotations

import importlib.util
import math
import time
import zlib
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = PROJECT_ROOT / "code/python"
EXTERNAL_DIR = PROJECT_ROOT / "data/external"
TABLE_DIR = PROJECT_ROOT / "outputs/tables"
DOCS_DIR = PROJECT_ROOT / "docs"
LOG_DIR = PROJECT_ROOT / "outputs/logs"

PAF_FILE = TABLE_DIR / "msa_paf_insufficient_premature_30_69_nhis2024.csv"
PAF_MC_FILE = TABLE_DIR / "msa_paf_insufficient_montecarlo_premature_30_69_nhis2024.csv"
DEATHS_FILE = EXTERNAL_DIR / "us_allcause_deaths_by_age_sex_premature_30_69.csv"
LIFE_SINGLE_FILE = EXTERNAL_DIR / "us_life_table_by_age_sex.csv"
MANUAL_DOC = DOCS_DIR / "external_mortality_manual_download_instructions_premature_30_69.md"
ISSUES = LOG_DIR / "issues_to_resolve.md"

DEATHS_OUT = TABLE_DIR / "msa_attributable_deaths_premature_30_69_nhis2024.csv"
YLL_OUT = TABLE_DIR / "msa_yll_premature_30_69_nhis2024.csv"
SUMMARY_OUT = TABLE_DIR / "msa_burden_summary_premature_30_69_nhis2024.csv"

TARGET_PERIOD = "premature_30_69"
MAIN_SCENARIO = "main_hr_target_30_69"
AGE_ORDER = ["30-34", "35-44", "45-54", "55-64", "65-69"]
SEX_ORDER = ["Female", "Male"]
REPRESENTATIVE_AGES = {"30-34": 32, "35-44": 40, "45-54": 50, "55-64": 60, "65-69": 67}
AGE_QUERY_COMPONENTS = {
    "30-34": {"age_var": "D158.V51", "values": ["30-34"], "label": "five_year_30_34"},
    "35-44": {"age_var": "D158.V5", "values": ["35-44"], "label": "ten_year_35_44"},
    "45-54": {"age_var": "D158.V5", "values": ["45-54"], "label": "ten_year_45_54"},
    "55-64": {"age_var": "D158.V5", "values": ["55-64"], "label": "ten_year_55_64"},
    "65-69": {"age_var": "D158.V51", "values": ["65-69"], "label": "five_year_65_69"},
}
N_DRAWS = 10_000
SEED = 20260429


def ensure_dirs() -> None:
    for path in [EXTERNAL_DIR, TABLE_DIR, DOCS_DIR, LOG_DIR]:
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


def read_required(path: Path, required: list[str]) -> pd.DataFrame:
    if not path.exists():
        stop("Missing premature 30-69 input", f"`{path.relative_to(PROJECT_ROOT)}` is missing.")
    df = pd.read_csv(path)
    missing = [col for col in required if col not in df.columns]
    if missing:
        stop("Premature 30-69 input missing columns", f"`{path.relative_to(PROJECT_ROOT)}` is missing: {', '.join(missing)}.")
    return df


def load_external_module():
    path = CODE_DIR / "09_download_or_prepare_external_mortality_lifetable.py"
    spec = importlib.util.spec_from_file_location("external_mortality_lifetable", path)
    if spec is None or spec.loader is None:
        stop("Cannot load external mortality helper", f"Could not load `{path.relative_to(PROJECT_ROOT)}`.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_manual_doc() -> None:
    MANUAL_DOC.write_text(
        """# Manual CDC WONDER Mortality Download Instructions For Premature 30-69 Analysis

Automatic CDC WONDER extraction did not complete. Do not fabricate death counts.

Use CDC WONDER: Underlying Cause of Death, 2018-2024, Single Race.

Required output: `data/external/us_allcause_deaths_by_age_sex_premature_30_69.csv`

Required columns:

- `year`
- `sex`
- `age_group`
- `deaths_allcause`
- `population`
- `source`
- `notes`

Manual query:

1. Dataset: Underlying Cause of Death, 2018-2024, Single Race.
2. Geography: United States.
3. Year: 2024 final mortality.
4. Cause of death: All Causes.
5. Group or filter by sex.
6. Export deaths and population for exact age groups 30-34, 35-44, 45-54, 55-64, and 65-69.
7. Save to `data/external/us_allcause_deaths_by_age_sex_premature_30_69.csv`.
""",
        encoding="utf-8",
    )


def has_required_mortality(path: Path) -> bool:
    required = ["year", "sex", "age_group", "deaths_allcause", "population", "source", "notes"]
    if not path.exists():
        return False
    try:
        df = pd.read_csv(path)
    except Exception:
        return False
    if any(col not in df.columns for col in required):
        return False
    expected = {(age, sex) for age in AGE_ORDER for sex in SEX_ORDER}
    found = set(zip(df["age_group"], df["sex"]))
    return expected.issubset(found)


def prepare_mortality() -> pd.DataFrame:
    required = ["year", "sex", "age_group", "deaths_allcause", "population", "source", "notes"]
    if has_required_mortality(DEATHS_FILE):
        df = pd.read_csv(DEATHS_FILE)
        return df[required].copy()

    write_manual_doc()
    helper = load_external_module()
    last_request_time = [0.0]
    rows = []
    try:
        for age_group in AGE_ORDER:
            component = AGE_QUERY_COMPONENTS[age_group]
            xml_path = helper.request_wonder_xml(
                year=2024,
                age_group=f"premature_30_69_{age_group}",
                component=component,
                min_interval=5.0,
                retry_wait=125.0,
                max_retries=2,
                last_request_time=last_request_time,
            )
            parsed = helper.parse_wonder_sex_rows(xml_path)
            for _, row in parsed.iterrows():
                rows.append(
                    {
                        "year": 2024,
                        "sex": row["sex"],
                        "age_group": age_group,
                        "deaths_allcause": int(round(float(row["deaths_allcause"]))),
                        "population": int(round(float(row["population"]))),
                        "source": helper.WONDER_SOURCE,
                        "notes": f"All causes; United States; final mortality; exact premature age group; component: {component['label']}",
                    }
                )
            time.sleep(0.2)
    except Exception as exc:
        stop(
            "CDC WONDER premature 30-69 mortality download failed",
            f"Automatic CDC WONDER extraction failed with `{exc}`. Manual instructions are in `{MANUAL_DOC.relative_to(PROJECT_ROOT)}`.",
        )

    mortality = pd.DataFrame(rows)
    expected = {(age, sex) for age in AGE_ORDER for sex in SEX_ORDER}
    found = set(zip(mortality["age_group"], mortality["sex"]))
    if found != expected:
        stop("Incomplete premature 30-69 mortality file", f"Missing strata: {sorted(expected - found)}.")
    mortality = mortality[required].sort_values(["age_group", "sex"]).reset_index(drop=True)
    mortality.to_csv(DEATHS_FILE, index=False)
    return mortality


def prepare_life_table() -> pd.DataFrame:
    life = read_required(LIFE_SINGLE_FILE, ["year", "sex", "age", "remaining_life_expectancy", "source", "notes"])
    life["age"] = pd.to_numeric(life["age"], errors="coerce")
    life["remaining_life_expectancy"] = pd.to_numeric(life["remaining_life_expectancy"], errors="coerce")
    rows = []
    for age_group, rep_age in REPRESENTATIVE_AGES.items():
        for sex in SEX_ORDER:
            match = life.loc[(life["sex"] == sex) & (life["age"] == rep_age)]
            if match.empty:
                stop("Missing representative life-table age", f"Missing NCHS life table row for {sex}, age {rep_age}.")
            row = match.iloc[0]
            rows.append(
                {
                    "life_table_year": int(row["year"]),
                    "sex": sex,
                    "age_group": age_group,
                    "representative_age": rep_age,
                    "remaining_life_expectancy": float(row["remaining_life_expectancy"]),
                    "life_table_source": row["source"],
                    "life_table_notes": f"Representative age method for premature 30-69: {age_group} uses age {rep_age}.",
                }
            )
    return pd.DataFrame(rows)


def summarize_draws(values: np.ndarray) -> tuple[float, float, float]:
    return float(np.median(values)), float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))


def group_key_rows(rows: pd.DataFrame) -> list[tuple[str, str, str, np.ndarray]]:
    groups: list[tuple[str, str, str, np.ndarray]] = [("overall", "all", "all", rows.index.to_numpy())]
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
        stop("Missing premature HR scenario", f"No rows found for `{scenario}`.")
    for col in ["prevalence_insufficient_msa", "hazard_ratio", "ci_lower", "ci_upper", "paf", "deaths_allcause", "population", "remaining_life_expectancy"]:
        rows[col] = pd.to_numeric(rows[col], errors="coerce")
    hr = float(rows["hazard_ratio"].iloc[0])
    lo = float(rows["ci_lower"].iloc[0])
    hi = float(rows["ci_upper"].iloc[0])
    se = (math.log(hi) - math.log(lo)) / (2 * 1.96)
    rng = np.random.default_rng(SEED + zlib.crc32(scenario.encode("utf-8")) % 100000)
    hr_draws = np.exp(rng.normal(math.log(hr), se, size=N_DRAWS))
    prevalence = rows["prevalence_insufficient_msa"].to_numpy(dtype=float)
    paf_draws = prevalence[None, :] * (hr_draws[:, None] - 1) / (1 + prevalence[None, :] * (hr_draws[:, None] - 1))
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
        death_med, death_lo, death_hi = summarize_draws(death_draws[:, idx].sum(axis=1))
        yll_med, yll_lo, yll_hi = summarize_draws(yll_draws[:, idx].sum(axis=1))
        common = {
            "rr_scenario": scenario,
            "target_period": TARGET_PERIOD,
            "stratum": stratum,
            "age_group": age_group,
            "sex": sex,
            "mortality_year": int(rows["year"].iloc[0]),
            "life_table_year": int(rows["life_table_year"].iloc[0]),
            "deaths_allcause": float(rows.loc[idx, "deaths_allcause"].sum()),
            "population": float(rows.loc[idx, "population"].sum()),
            "n_draws": N_DRAWS,
        }
        death_records.append(
            {
                **common,
                "attributable_deaths": float(rows.loc[idx, "attributable_deaths"].sum()),
                "attributable_deaths_median": death_med,
                "attributable_deaths_p2_5": death_lo,
                "attributable_deaths_p97_5": death_hi,
                "mortality_source": rows["source"].iloc[0],
            }
        )
        yll_records.append(
            {
                **common,
                "remaining_life_expectancy": np.nan if stratum != "age_group_sex" else float(rows.loc[idx, "remaining_life_expectancy"].iloc[0]),
                "representative_age": np.nan if stratum != "age_group_sex" else int(rows.loc[idx, "representative_age"].iloc[0]),
                "yll": float(rows.loc[idx, "yll"].sum()),
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
                    "attributable_deaths": float(rows.loc[idx, "attributable_deaths"].sum()),
                    "attributable_deaths_median": death_med,
                    "attributable_deaths_p2_5": death_lo,
                    "attributable_deaths_p97_5": death_hi,
                    "yll": float(rows.loc[idx, "yll"].sum()),
                    "yll_median": yll_med,
                    "yll_p2_5": yll_lo,
                    "yll_p97_5": yll_hi,
                }
            )
    return pd.DataFrame(death_records), pd.DataFrame(yll_records), pd.DataFrame(summary_records)


def main() -> None:
    ensure_dirs()
    paf = read_required(PAF_FILE, ["target_period", "stratum", "age_group", "sex", "rr_scenario", "prevalence_insufficient_msa", "hazard_ratio", "ci_lower", "ci_upper", "paf"])
    _ = read_required(PAF_MC_FILE, ["target_period", "stratum", "age_group", "sex", "rr_scenario", "n_draws"])
    paf = paf.loc[(paf["target_period"] == TARGET_PERIOD) & (paf["stratum"] == "age_group_sex")].copy()
    expected = {(age, sex) for age in AGE_ORDER for sex in SEX_ORDER}
    found = set(zip(paf["age_group"], paf["sex"]))
    if found != expected:
        stop("Premature 30-69 PAF strata mismatch", f"Expected {sorted(expected)}, found {sorted(found)}.")

    mortality = prepare_mortality()
    life = prepare_life_table()
    merged = paf.merge(mortality, on=["age_group", "sex"], how="left", suffixes=("", "_mortality"))
    if "year_mortality" in merged.columns:
        merged["year"] = merged["year_mortality"]
    merged = merged.merge(life, on=["age_group", "sex"], how="left")
    if merged[["deaths_allcause", "population", "remaining_life_expectancy"]].isna().any().any():
        missing = merged.loc[merged[["deaths_allcause", "population", "remaining_life_expectancy"]].isna().any(axis=1), ["age_group", "sex"]]
        stop("Premature 30-69 mortality/YLL inputs missing", f"Missing matched inputs for: {missing.to_dict(orient='records')}.")

    death_frames = []
    yll_frames = []
    summary_frames = []
    for scenario in sorted(merged["rr_scenario"].dropna().unique()):
        d, y, s = compute_for_scenario(merged, scenario)
        death_frames.append(d)
        yll_frames.append(y)
        summary_frames.append(s)
    deaths_out = pd.concat(death_frames, ignore_index=True)
    yll_out = pd.concat(yll_frames, ignore_index=True)
    summary_out = pd.concat(summary_frames, ignore_index=True)
    deaths_out.to_csv(DEATHS_OUT, index=False)
    yll_out.to_csv(YLL_OUT, index=False)
    summary_out.to_csv(SUMMARY_OUT, index=False)
    main = summary_out.loc[summary_out["rr_scenario"] == MAIN_SCENARIO].iloc[0]
    print(f"Wrote {DEATHS_FILE.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {DEATHS_OUT.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {YLL_OUT.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {SUMMARY_OUT.relative_to(PROJECT_ROOT)}")
    print(f"Premature 30-69 all-cause deaths: {main['deaths_allcause']:.0f}")
    print(f"Premature 30-69 attributable deaths: {main['attributable_deaths']:.0f}")
    print(f"Premature 30-69 YLL: {main['yll']:.0f}")


if __name__ == "__main__":
    main()
