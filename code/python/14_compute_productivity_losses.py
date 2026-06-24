"""Estimate productivity losses if documented economic inputs are available.

This module is intentionally conservative. It computes human-capital
productivity losses only when an official, documented age-sex input file exists:

    data/external/us_productivity_inputs_by_age_sex.csv

If that file is absent, the script creates a template and manual download
instructions, writes a report explaining that productivity losses were not
computed, and exits without fabricating costs.
"""

from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TABLE_DIR = PROJECT_ROOT / "outputs/tables"
EXTERNAL_DIR = PROJECT_ROOT / "data/external"
DOCS_DIR = PROJECT_ROOT / "docs"
LOG_DIR = PROJECT_ROOT / "outputs/logs"

INPUT_FILE = EXTERNAL_DIR / "us_productivity_inputs_by_age_sex.csv"
TEMPLATE_FILE = EXTERNAL_DIR / "us_productivity_inputs_by_age_sex_template.csv"
DOC_FILE = DOCS_DIR / "external_productivity_manual_download_instructions.md"
ISSUES = LOG_DIR / "issues_to_resolve.md"

PAF_FILE = TABLE_DIR / "msa_paf_insufficient_using_nhis2024.csv"
DEATHS_FILE = EXTERNAL_DIR / "us_allcause_deaths_by_age_sex.csv"
ATTR_DEATHS_FILE = TABLE_DIR / "msa_attributable_deaths_nhis2024.csv"

OUT_TOTAL = TABLE_DIR / "msa_productivity_losses_nhis2024.csv"
OUT_MC = TABLE_DIR / "msa_productivity_losses_montecarlo_nhis2024.csv"
OUT_BY_AGE_SEX = TABLE_DIR / "msa_productivity_losses_by_age_sex_nhis2024.csv"
OUT_REPORT = TABLE_DIR / "msa_productivity_losses_report.md"

ACS_SINGLE_AGE_INPUT = EXTERNAL_DIR / "us_productivity_inputs_by_single_age_sex.csv"
ACS_GROUP_INPUT = EXTERNAL_DIR / "us_productivity_inputs_by_age_sex_premature_30_69.csv"
ACS_MANUAL_DOC = DOCS_DIR / "external_productivity_acs_pums_manual_download_instructions.md"
PAF_PREMATURE_FILE = TABLE_DIR / "msa_paf_insufficient_premature_30_69_nhis2024.csv"
DEATHS_PREMATURE_FILE = EXTERNAL_DIR / "us_allcause_deaths_by_age_sex_premature_30_69.csv"
ATTR_DEATHS_PREMATURE_FILE = TABLE_DIR / "msa_attributable_deaths_premature_30_69_nhis2024.csv"
OUT_TOTAL_PREMATURE = TABLE_DIR / "msa_productivity_losses_premature_30_69_nhis2024.csv"
OUT_MC_PREMATURE = TABLE_DIR / "msa_productivity_losses_montecarlo_premature_30_69_nhis2024.csv"
OUT_BY_AGE_SEX_PREMATURE = TABLE_DIR / "msa_productivity_losses_by_age_sex_premature_30_69_nhis2024.csv"
OUT_REPORT_PREMATURE = TABLE_DIR / "msa_productivity_losses_report_premature_30_69.md"

PRIMARY_SCENARIO = "main_strata_sex_year"
PRIMARY_PREMATURE_SCENARIO = "main_hr_target_30_69"
AGE_ORDER = ["18-34", "35-44", "45-54", "55-64", "65-74", "75+"]
PREMATURE_AGE_ORDER = ["30-34", "35-44", "45-54", "55-64", "65-69"]
PRODUCTIVE_AGE_MAIN = ["18-34", "35-44", "45-54", "55-64"]
PRODUCTIVE_AGE_SENSITIVITY = ["18-34", "35-44", "45-54", "55-64", "65-74"]
DISCOUNT_RATES = [0.03, 0.0, 0.05]
SEED = 20260429
N_DRAWS = 10_000
ACS_API = "https://api.census.gov/data/2024/acs/acs1/pums"
ACS_SOURCE = "U.S. Census Bureau, 2024 ACS 1-year PUMS person records via Census Microdata API"


def ensure_dirs() -> None:
    for path in [TABLE_DIR, EXTERNAL_DIR, DOCS_DIR, LOG_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def append_issue_once(title: str, message: str) -> None:
    ensure_dirs()
    old = ISSUES.read_text(encoding="utf-8") if ISSUES.exists() else "# Issues to Resolve\n\n"
    if title in old:
        return
    stamp = datetime.now().isoformat(timespec="seconds")
    ISSUES.write_text(old.rstrip() + f"\n\n## {stamp} - {title}\n\n{message.rstrip()}\n", encoding="utf-8")


def read_required(path: Path, required: list[str]) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"Required file not found: {path.relative_to(PROJECT_ROOT)}")
    df = pd.read_csv(path)
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise SystemExit(f"{path.relative_to(PROJECT_ROOT)} is missing required columns: {', '.join(missing)}")
    return df


def write_template_and_docs() -> None:
    if not TEMPLATE_FILE.exists():
        rows = []
        for sex in ["Female", "Male"]:
            for age_group in AGE_ORDER:
                rows.append(
                    {
                        "year": "",
                        "sex": sex,
                        "age_group": age_group,
                        "employment_rate": "",
                        "annual_earnings": "",
                        "productive_years_remaining": "",
                        "source": "",
                        "notes": "",
                    }
                )
        pd.DataFrame(rows).to_csv(TEMPLATE_FILE, index=False)

    text = """# External Productivity Inputs Needed

Productivity losses have not been computed because the project does not yet
contain an official, documented input file at:

`data/external/us_productivity_inputs_by_age_sex.csv`

Create that file with these columns:

- `year`
- `sex`
- `age_group`
- `employment_rate`
- `annual_earnings`
- `productive_years_remaining`
- `source`
- `notes`

Required age groups are 18-34, 35-44, 45-54, 55-64, 65-74, and 75+ by sex.
The main analysis will use ages 18-64. The 65-74 group is used only as a
sensitivity analysis when official employment and earnings inputs are present.
The 75+ group is not assigned productivity losses unless a manuscript decision
explicitly justifies doing so with official data.

Recommended official sources:

1. BLS Current Population Survey annual averages for employment by age and sex.
   Candidate tables include annual-average CPS employment status tables and
   employed/unemployed full-time and part-time worker tables.
   Start here: https://www.bls.gov/cps/tables.htm
2. BLS CPS annual-average usual weekly earnings by age and sex.
   Candidate table: CPS annual average table 37, median weekly earnings of
   full-time wage and salary workers by selected characteristics.
   2024 table: https://www.bls.gov/cps/data/aa2024/cpsaat37.htm
3. If choosing annual earnings or labor income from Census/ACS instead of BLS
   weekly earnings, use a documented ACS table or PUMS extraction and record the
   exact table, variables, vintage, and conversion to annual dollars.

Do not fill the template with approximate or invented values. Every row should
cite the official source and year used. If weekly earnings are used, document the
annualization rule, for example `annual_earnings = weekly_earnings * 52`.
"""
    DOC_FILE.write_text(text, encoding="utf-8")


def write_not_computed_report() -> None:
    text = f"""# Productivity Losses Report

Generated: {datetime.now().isoformat(timespec="seconds")}

Productivity losses were not computed because the required official age-sex
economic input file is not present:

`data/external/us_productivity_inputs_by_age_sex.csv`

The script created:

- `data/external/us_productivity_inputs_by_age_sex_template.csv`
- `docs/external_productivity_manual_download_instructions.md`

No productivity-cost estimates were fabricated. Once official employment rates,
annual earnings or labor income, productive years remaining, source names, and
notes are populated, rerun:

```powershell
python code/python/14_compute_productivity_losses.py
```

The intended interpretation is: productivity losses associated with premature
mortality potentially attributable to insufficient MSA under the modelled
counterfactual.
"""
    OUT_REPORT.write_text(text, encoding="utf-8")


def age_group_30_69(age: pd.Series) -> pd.Series:
    out = pd.Series(pd.NA, index=age.index, dtype="object")
    out.loc[age.between(30, 34, inclusive="both")] = "30-34"
    out.loc[age.between(35, 44, inclusive="both")] = "35-44"
    out.loc[age.between(45, 54, inclusive="both")] = "45-54"
    out.loc[age.between(55, 64, inclusive="both")] = "55-64"
    out.loc[age.between(65, 69, inclusive="both")] = "65-69"
    return out


def weighted_median(values: pd.Series, weights: pd.Series) -> float:
    mask = values.notna() & weights.notna() & (weights > 0)
    if not mask.any():
        return np.nan
    v = values.loc[mask].to_numpy(dtype=float)
    w = weights.loc[mask].to_numpy(dtype=float)
    order = np.argsort(v)
    v = v[order]
    w = w[order]
    cutoff = w.sum() / 2.0
    return float(v[np.searchsorted(np.cumsum(w), cutoff, side="left")])


def acs_adjustment_factor(values: pd.Series) -> pd.Series:
    raw = pd.to_numeric(values, errors="coerce")
    return np.where(raw > 1000, raw / 1_000_000.0, raw)


def query_acs_age(age: int) -> pd.DataFrame:
    params = {"get": "AGEP,SEX,ESR,WAGP,PERNP,PWGTP,ADJINC", "AGEP": str(age)}
    response = requests.get(ACS_API, params=params, timeout=60)
    response.raise_for_status()
    data = response.json()
    if not data or len(data) < 2:
        return pd.DataFrame(columns=["AGEP", "SEX", "ESR", "WAGP", "PERNP", "PWGTP", "ADJINC"])
    header = data[0]
    records = data[1:]
    df = pd.DataFrame(records, columns=header)
    if "AGEP" in df.columns and isinstance(df["AGEP"], pd.DataFrame):
        df = df.loc[:, ~df.columns.duplicated()]
    return df


def write_acs_manual_doc(error: str) -> None:
    ACS_MANUAL_DOC.write_text(
        f"""# ACS PUMS Productivity Manual Download Instructions

Automatic ACS PUMS download failed or was unavailable. Sanitized error:

```text
{error}
```

Do not fabricate economic inputs. Prepare official 2024 ACS 1-year PUMS person
records with these variables:

- `AGEP`
- `SEX`
- `ESR`
- `WAGP`
- `PERNP`
- `PWGTP`
- `ADJINC`

Preferred source:
`https://api.census.gov/data/2024/acs/acs1/pums`

Alternative bulk source:
`https://www2.census.gov/programs-surveys/acs/data/pums/2024/1-Year/`

Create:

- `data/external/us_productivity_inputs_by_single_age_sex.csv`
- `data/external/us_productivity_inputs_by_age_sex_premature_30_69.csv`

Use exact age groups 30-34, 35-44, 45-54, 55-64, and 65-69 by sex. Use person
weights `PWGTP`, ACS employment status `ESR`, and inflation-adjusted `PERNP` and
`WAGP` using `ADJINC`. Document all coding choices and sources.
""",
        encoding="utf-8",
    )


def build_acs_productivity_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    required_group = [
        "year",
        "sex",
        "age_group",
        "employment_rate",
        "annual_earnings_pernp_mean",
        "annual_earnings_pernp_median",
        "annual_earnings_wagp_mean",
        "annual_earnings_wagp_median",
        "productive_years_remaining_to_65",
        "productive_years_remaining_to_70",
        "productive_years_remaining_to_75",
        "source",
        "notes",
    ]
    required_single = ["year", "sex", "age"] + [col for col in required_group if col not in {"year", "sex", "age_group"}]
    if ACS_GROUP_INPUT.exists() and ACS_SINGLE_AGE_INPUT.exists():
        group = pd.read_csv(ACS_GROUP_INPUT)
        single = pd.read_csv(ACS_SINGLE_AGE_INPUT)
        if all(col in group.columns for col in required_group) and all(col in single.columns for col in required_single):
            return group, single

    try:
        frames = [query_acs_age(age) for age in range(30, 70)]
        raw = pd.concat(frames, ignore_index=True)
    except Exception as exc:
        write_acs_manual_doc(str(exc))
        append_issue_once(
            "ACS PUMS productivity download failed",
            f"Productivity losses for premature 30-69 were not computed because ACS PUMS automatic download failed. Manual instructions were written to `docs/external_productivity_acs_pums_manual_download_instructions.md`. Sanitized error: `{exc}`.",
        )
        raise SystemExit("ACS PUMS productivity inputs unavailable; manual instructions were created.")

    for col in ["AGEP", "SEX", "ESR", "WAGP", "PERNP", "PWGTP", "ADJINC"]:
        raw[col] = pd.to_numeric(raw[col], errors="coerce")
    raw = raw.loc[raw["AGEP"].between(30, 69, inclusive="both") & raw["PWGTP"].notna() & (raw["PWGTP"] > 0)].copy()
    raw["sex"] = raw["SEX"].map({1: "Male", 2: "Female"})
    raw["age"] = raw["AGEP"].astype(int)
    raw["age_group"] = age_group_30_69(raw["AGEP"])
    raw["employed"] = raw["ESR"].isin([1, 2, 4, 5]).astype(int)
    raw["adjinc_factor"] = acs_adjustment_factor(raw["ADJINC"])
    raw["pernp_adjusted"] = (raw["PERNP"] * raw["adjinc_factor"]).clip(lower=0)
    raw["wagp_adjusted"] = (raw["WAGP"] * raw["adjinc_factor"]).clip(lower=0)
    raw = raw.dropna(subset=["sex", "age_group"])

    single_rows = []
    for (sex, age), sub in raw.groupby(["sex", "age"], sort=True):
        weights = sub["PWGTP"]
        employed = sub["employed"] == 1
        employed_w = weights.loc[employed]
        pernp = sub.loc[employed, "pernp_adjusted"]
        wagp = sub.loc[employed, "wagp_adjusted"]
        single_rows.append(
            {
                "year": 2024,
                "sex": sex,
                "age": int(age),
                "employment_rate": float((weights * sub["employed"]).sum() / weights.sum()),
                "annual_earnings_pernp_mean": float(np.average(pernp, weights=employed_w)) if len(pernp) else np.nan,
                "annual_earnings_pernp_median": weighted_median(pernp, employed_w),
                "annual_earnings_wagp_mean": float(np.average(wagp, weights=employed_w)) if len(wagp) else np.nan,
                "annual_earnings_wagp_median": weighted_median(wagp, employed_w),
                "productive_years_remaining_to_65": max(0, 65 - int(age)),
                "productive_years_remaining_to_70": max(0, 70 - int(age)),
                "productive_years_remaining_to_75": max(0, 75 - int(age)),
                "source": ACS_SOURCE,
                "notes": "Employment is ESR in 1,2,4,5. Earnings are ACS PERNP/WAGP adjusted by ADJINC and clipped at zero for valuation.",
            }
        )
    single = pd.DataFrame(single_rows)

    group_rows = []
    for (sex, age_group), sub in raw.groupby(["sex", "age_group"], sort=True):
        weights = sub["PWGTP"]
        employed = sub["employed"] == 1
        employed_w = weights.loc[employed]
        pernp = sub.loc[employed, "pernp_adjusted"]
        wagp = sub.loc[employed, "wagp_adjusted"]
        group_rows.append(
            {
                "year": 2024,
                "sex": sex,
                "age_group": age_group,
                "employment_rate": float((weights * sub["employed"]).sum() / weights.sum()),
                "annual_earnings_pernp_mean": float(np.average(pernp, weights=employed_w)) if len(pernp) else np.nan,
                "annual_earnings_pernp_median": weighted_median(pernp, employed_w),
                "annual_earnings_wagp_mean": float(np.average(wagp, weights=employed_w)) if len(wagp) else np.nan,
                "annual_earnings_wagp_median": weighted_median(wagp, employed_w),
                "productive_years_remaining_to_65": float(np.average(np.maximum(0, 65 - sub["age"]), weights=weights)),
                "productive_years_remaining_to_70": float(np.average(np.maximum(0, 70 - sub["age"]), weights=weights)),
                "productive_years_remaining_to_75": float(np.average(np.maximum(0, 75 - sub["age"]), weights=weights)),
                "source": ACS_SOURCE,
                "notes": "Age-group inputs are PWGTP-weighted from ACS PUMS 2024 person records; earnings among employed persons.",
            }
        )
    group = pd.DataFrame(group_rows)
    expected = {(age, sex) for age in PREMATURE_AGE_ORDER for sex in ["Female", "Male"]}
    found = set(zip(group["age_group"], group["sex"]))
    if found != expected:
        raise SystemExit(f"ACS productivity inputs missing strata: {sorted(expected - found)}")
    group = group[required_group].sort_values(["age_group", "sex"]).reset_index(drop=True)
    single = single[required_single].sort_values(["age", "sex"]).reset_index(drop=True)
    group.to_csv(ACS_GROUP_INPUT, index=False)
    single.to_csv(ACS_SINGLE_AGE_INPUT, index=False)
    return group, single


def make_premature_paf_draws(paf: pd.DataFrame) -> pd.DataFrame:
    strata = paf.loc[(paf["rr_scenario"] == PRIMARY_PREMATURE_SCENARIO) & (paf["stratum"] == "age_group_sex")].copy()
    hr = float(strata["hazard_ratio"].dropna().iloc[0])
    lo = float(strata["ci_lower"].dropna().iloc[0])
    hi = float(strata["ci_upper"].dropna().iloc[0])
    se_log_hr = (math.log(hi) - math.log(lo)) / (2.0 * 1.96)
    rng = np.random.default_rng(SEED)
    hr_draws = np.exp(rng.normal(math.log(hr), se_log_hr, size=N_DRAWS))
    rows = []
    for _, row in strata.iterrows():
        p = float(row["prevalence_insufficient_msa"])
        draws = p * (hr_draws - 1.0) / (p * (hr_draws - 1.0) + 1.0)
        for draw_id, value in enumerate(draws, start=1):
            rows.append({"draw_id": draw_id, "age_group": row["age_group"], "sex": row["sex"], "paf_draw": float(value)})
    return pd.DataFrame(rows)


def compute_premature_productivity(group_inputs: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    attr = read_required(ATTR_DEATHS_PREMATURE_FILE, ["rr_scenario", "stratum", "age_group", "sex", "attributable_deaths"])
    deaths = read_required(DEATHS_PREMATURE_FILE, ["age_group", "sex", "deaths_allcause"])
    paf = read_required(PAF_PREMATURE_FILE, ["rr_scenario", "stratum", "age_group", "sex", "prevalence_insufficient_msa", "hazard_ratio", "ci_lower", "ci_upper"])
    attr = attr.loc[(attr["rr_scenario"] == PRIMARY_PREMATURE_SCENARIO) & (attr["stratum"] == "age_group_sex")].copy()
    attr["attributable_deaths"] = pd.to_numeric(attr["attributable_deaths"], errors="coerce")
    deaths["deaths_allcause"] = pd.to_numeric(deaths["deaths_allcause"], errors="coerce")
    base = attr.merge(group_inputs, on=["age_group", "sex"], how="left", validate="one_to_one")
    if base[["employment_rate", "annual_earnings_pernp_mean", "productive_years_remaining_to_65"]].isna().any().any():
        raise SystemExit("Premature productivity inputs have missing matched strata.")

    detail_rows = []
    for earnings_measure in ["pernp_mean", "wagp_mean"]:
        earnings_col = "annual_earnings_pernp_mean" if earnings_measure == "pernp_mean" else "annual_earnings_wagp_mean"
        for horizon in [65, 70, 75]:
            years_col = f"productive_years_remaining_to_{horizon}"
            for discount_rate in DISCOUNT_RATES:
                tmp = base.copy()
                tmp["analysis"] = "premature_30_69"
                tmp["earnings_measure"] = earnings_measure
                tmp["productive_horizon"] = horizon
                tmp["discount_rate"] = discount_rate
                tmp["present_value_productive_year_factor"] = tmp[years_col].map(lambda years: present_value_factor(float(years), discount_rate))
                tmp["productivity_loss"] = (
                    tmp["attributable_deaths"]
                    * tmp["employment_rate"]
                    * tmp[earnings_col]
                    * tmp["present_value_productive_year_factor"]
                )
                detail_rows.append(tmp)
    detail = pd.concat(detail_rows, ignore_index=True)
    totals = (
        detail.groupby(["analysis", "earnings_measure", "productive_horizon", "discount_rate"], as_index=False)
        .agg(
            productivity_loss=("productivity_loss", "sum"),
            attributable_deaths_included=("attributable_deaths", "sum"),
            economic_input_year=("year", "max"),
        )
        .sort_values(["earnings_measure", "productive_horizon", "discount_rate"])
    )

    paf_draws = make_premature_paf_draws(paf)
    mc_base = deaths.merge(group_inputs, on=["age_group", "sex"], how="inner", validate="one_to_one").merge(paf_draws, on=["age_group", "sex"], how="inner")
    mc_base["attributable_deaths_draw"] = mc_base["paf_draw"] * mc_base["deaths_allcause"]
    mc_rows = []
    for earnings_measure in ["pernp_mean", "wagp_mean"]:
        earnings_col = "annual_earnings_pernp_mean" if earnings_measure == "pernp_mean" else "annual_earnings_wagp_mean"
        for horizon in [65, 70, 75]:
            years_col = f"productive_years_remaining_to_{horizon}"
            for discount_rate in DISCOUNT_RATES:
                sub = mc_base.copy()
                sub["pv_factor"] = sub[years_col].map(lambda years: present_value_factor(float(years), discount_rate))
                sub["loss_draw"] = sub["attributable_deaths_draw"] * sub["employment_rate"] * sub[earnings_col] * sub["pv_factor"]
                draw_totals = sub.groupby("draw_id")["loss_draw"].sum()
                mc_rows.append(
                    {
                        "analysis": "premature_30_69",
                        "earnings_measure": earnings_measure,
                        "productive_horizon": horizon,
                        "discount_rate": discount_rate,
                        "n_draws": int(draw_totals.shape[0]),
                        "productivity_loss_median": max(0.0, float(np.nanmedian(draw_totals))),
                        "productivity_loss_p2_5": max(0.0, float(np.nanpercentile(draw_totals, 2.5))),
                        "productivity_loss_p97_5": float(np.nanpercentile(draw_totals, 97.5)),
                    }
                )
    return totals, pd.DataFrame(mc_rows), detail


def write_premature_productivity_report(totals: pd.DataFrame, mc: pd.DataFrame, computed: bool, reason: str = "") -> None:
    if not computed:
        OUT_REPORT_PREMATURE.write_text(
            f"""# Premature 30-69 Productivity Losses Report

Generated: {datetime.now().isoformat(timespec="seconds")}

Productivity losses were not computed. {reason}

No productivity costs were fabricated. Use official ACS PUMS inputs before
reporting productivity losses associated with premature mortality potentially
attributable to insufficient MSA under the modelled counterfactual.
""",
            encoding="utf-8",
        )
        return
    main = totals.loc[(totals["earnings_measure"] == "pernp_mean") & (totals["productive_horizon"] == 65) & (np.isclose(totals["discount_rate"], 0.03))].iloc[0]
    main_mc = mc.loc[(mc["earnings_measure"] == "pernp_mean") & (mc["productive_horizon"] == 65) & (np.isclose(mc["discount_rate"], 0.03))].iloc[0]
    OUT_REPORT_PREMATURE.write_text(
        f"""# Premature 30-69 Productivity Losses Report

Generated: {datetime.now().isoformat(timespec="seconds")}

## Method

The primary valuation uses a human-capital approach for deaths occurring at
ages 30-69, with productive years valued to age 65, a 3% discount rate, and ACS
PUMS 2024 `PERNP` as the main earnings measure. Sensitivities use `WAGP`,
productive horizons to ages 70 and 75, and discount rates of 0% and 5%.

## Main Result

Productivity losses associated with premature mortality potentially attributable
to insufficient MSA under the modelled counterfactual were
${main['productivity_loss']:,.0f}. Monte Carlo interval:
${main_mc['productivity_loss_p2_5']:,.0f} to ${main_mc['productivity_loss_p97_5']:,.0f}.

## Inputs

- Economic input: 2024 ACS 1-year PUMS person records.
- Source access: U.S. Census Bureau Microdata API `{ACS_API}`.
- Variables: AGEP, SEX, ESR, WAGP, PERNP, PWGTP, ADJINC.
- Employment coding: ESR 1, 2, 4, or 5.
- Earnings: adjusted by ADJINC and clipped at zero for valuation.

## Limitations

- Economic inputs are treated as fixed; uncertainty reflects HR uncertainty only.
- This is a productivity valuation, not a healthcare-cost estimate.
- Results should not be described as direct cost savings.
""",
        encoding="utf-8",
    )


def run_premature_productivity_module() -> bool:
    try:
        group_inputs, _single = build_acs_productivity_inputs()
        totals, mc, detail = compute_premature_productivity(group_inputs)
    except SystemExit as exc:
        write_premature_productivity_report(pd.DataFrame(), pd.DataFrame(), computed=False, reason=str(exc))
        return False
    totals.to_csv(OUT_TOTAL_PREMATURE, index=False)
    mc.to_csv(OUT_MC_PREMATURE, index=False)
    detail.to_csv(OUT_BY_AGE_SEX_PREMATURE, index=False)
    write_premature_productivity_report(totals, mc, computed=True)
    print(f"Wrote {ACS_GROUP_INPUT.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {ACS_SINGLE_AGE_INPUT.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {OUT_TOTAL_PREMATURE.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {OUT_MC_PREMATURE.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {OUT_BY_AGE_SEX_PREMATURE.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {OUT_REPORT_PREMATURE.relative_to(PROJECT_ROOT)}")
    return True


def present_value_factor(years: float, discount_rate: float) -> float:
    if pd.isna(years) or years <= 0:
        return 0.0
    if discount_rate == 0:
        return float(years)
    return float((1.0 - (1.0 + discount_rate) ** (-years)) / discount_rate)


def load_productivity_inputs() -> pd.DataFrame:
    required = [
        "year",
        "sex",
        "age_group",
        "employment_rate",
        "annual_earnings",
        "productive_years_remaining",
        "source",
        "notes",
    ]
    df = read_required(INPUT_FILE, required)
    for col in ["employment_rate", "annual_earnings", "productive_years_remaining"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    bad = df[["employment_rate", "annual_earnings", "productive_years_remaining"]].isna().any(axis=1)
    if bad.any():
        raise SystemExit("Productivity input file has missing or nonnumeric employment, earnings, or productive-years values.")
    if ((df["employment_rate"] < 0) | (df["employment_rate"] > 1)).any():
        raise SystemExit("Productivity input employment_rate must be scaled 0-1.")
    if (df["annual_earnings"] < 0).any() or (df["productive_years_remaining"] < 0).any():
        raise SystemExit("Productivity input annual_earnings and productive_years_remaining must be nonnegative.")
    return df


def load_burden_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    attr = read_required(
        ATTR_DEATHS_FILE,
        ["rr_scenario", "stratum", "age_group", "sex", "attributable_deaths"],
    )
    deaths = read_required(DEATHS_FILE, ["age_group", "sex", "deaths_allcause"])
    paf = read_required(
        PAF_FILE,
        ["rr_scenario", "stratum", "age_group", "sex", "prevalence_insufficient_msa", "hazard_ratio", "ci_lower", "ci_upper"],
    )
    attr = attr.loc[(attr["rr_scenario"] == PRIMARY_SCENARIO) & (attr["stratum"] == "age_group_sex")].copy()
    attr["attributable_deaths"] = pd.to_numeric(attr["attributable_deaths"], errors="coerce")
    deaths["deaths_allcause"] = pd.to_numeric(deaths["deaths_allcause"], errors="coerce")
    return attr, deaths, paf


def make_paf_draws(paf: pd.DataFrame, n_draws: int = N_DRAWS) -> pd.DataFrame:
    strata = paf.loc[(paf["rr_scenario"] == PRIMARY_SCENARIO) & (paf["stratum"] == "age_group_sex")].copy()
    hr = float(strata["hazard_ratio"].dropna().iloc[0])
    lo = float(strata["ci_lower"].dropna().iloc[0])
    hi = float(strata["ci_upper"].dropna().iloc[0])
    se_log_hr = (math.log(hi) - math.log(lo)) / (2.0 * 1.96)
    rng = np.random.default_rng(SEED)
    hr_draws = np.exp(rng.normal(math.log(hr), se_log_hr, size=n_draws))
    strata["prevalence_insufficient_msa"] = pd.to_numeric(strata["prevalence_insufficient_msa"], errors="coerce")
    rows = []
    for _, row in strata.iterrows():
        p = float(row["prevalence_insufficient_msa"])
        paf_draw = p * (hr_draws - 1.0) / (p * (hr_draws - 1.0) + 1.0)
        for draw_id, value in enumerate(paf_draw, start=1):
            rows.append({"draw_id": draw_id, "age_group": row["age_group"], "sex": row["sex"], "paf_draw": value})
    return pd.DataFrame(rows)


def compute_losses(productivity: pd.DataFrame, attr: pd.DataFrame, deaths: pd.DataFrame, paf: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    base = attr.merge(productivity, on=["age_group", "sex"], how="left", validate="one_to_one")
    missing = base.loc[base[["employment_rate", "annual_earnings", "productive_years_remaining"]].isna().any(axis=1), ["age_group", "sex"]]
    if not missing.empty:
        raise SystemExit(f"Missing productivity inputs for strata: {missing.to_dict(orient='records')}")

    detail_rows = []
    for analysis, ages in [
        ("main_ages_18_64", PRODUCTIVE_AGE_MAIN),
        ("sensitivity_ages_18_74", PRODUCTIVE_AGE_SENSITIVITY),
    ]:
        sub = base.loc[base["age_group"].isin(ages)].copy()
        for discount_rate in DISCOUNT_RATES:
            pv = sub["productive_years_remaining"].map(lambda years: present_value_factor(float(years), discount_rate))
            loss = sub["attributable_deaths"] * sub["employment_rate"] * sub["annual_earnings"] * pv
            tmp = sub.copy()
            tmp["analysis"] = analysis
            tmp["discount_rate"] = discount_rate
            tmp["present_value_productive_year_factor"] = pv
            tmp["productivity_loss"] = loss
            detail_rows.append(tmp)
    detail = pd.concat(detail_rows, ignore_index=True)

    totals = (
        detail.groupby(["analysis", "discount_rate"], as_index=False)
        .agg(
            productivity_loss=("productivity_loss", "sum"),
            attributable_deaths_included=("attributable_deaths", "sum"),
            annual_earnings_weighted_mean=("annual_earnings", "mean"),
            economic_input_year=("year", "max"),
        )
        .sort_values(["analysis", "discount_rate"])
    )

    paf_draws = make_paf_draws(paf)
    mc_base = deaths.merge(productivity, on=["age_group", "sex"], how="inner", validate="one_to_one")
    mc_base = mc_base.merge(paf_draws, on=["age_group", "sex"], how="inner")
    mc_base["deaths_allcause"] = pd.to_numeric(mc_base["deaths_allcause"], errors="coerce")
    mc_rows = []
    for analysis, ages in [
        ("main_ages_18_64", PRODUCTIVE_AGE_MAIN),
        ("sensitivity_ages_18_74", PRODUCTIVE_AGE_SENSITIVITY),
    ]:
        sub = mc_base.loc[mc_base["age_group"].isin(ages)].copy()
        sub["attributable_deaths_draw"] = sub["paf_draw"] * sub["deaths_allcause"]
        for discount_rate in DISCOUNT_RATES:
            sub["pv_factor"] = sub["productive_years_remaining"].map(lambda years: present_value_factor(float(years), discount_rate))
            sub["loss_draw"] = sub["attributable_deaths_draw"] * sub["employment_rate"] * sub["annual_earnings"] * sub["pv_factor"]
            draw_totals = sub.groupby("draw_id")["loss_draw"].sum()
            mc_rows.append(
                {
                    "analysis": analysis,
                    "discount_rate": discount_rate,
                    "n_draws": int(draw_totals.shape[0]),
                    "productivity_loss_median": max(0.0, float(np.nanmedian(draw_totals))),
                    "productivity_loss_p2_5": max(0.0, float(np.nanpercentile(draw_totals, 2.5))),
                    "productivity_loss_p97_5": float(np.nanpercentile(draw_totals, 97.5)),
                }
            )
    mc = pd.DataFrame(mc_rows).sort_values(["analysis", "discount_rate"])
    return totals, mc, detail


def write_computed_report(totals: pd.DataFrame, mc: pd.DataFrame, productivity: pd.DataFrame) -> None:
    main = totals.loc[(totals["analysis"] == "main_ages_18_64") & (totals["discount_rate"] == 0.03)].iloc[0]
    main_mc = mc.loc[(mc["analysis"] == "main_ages_18_64") & (mc["discount_rate"] == 0.03)].iloc[0]
    sources = "; ".join(sorted(str(x) for x in productivity["source"].dropna().unique()))
    text = f"""# Productivity Losses Report

Generated: {datetime.now().isoformat(timespec="seconds")}

## Method

The primary valuation uses a human-capital approach for premature mortality
associated with insufficient MSA under the modelled counterfactual. The main
analysis includes deaths ages 18-64. A sensitivity analysis includes ages 65-74
when official employment and earnings inputs are present.

Productivity loss per stratum is:

`attributable deaths * employment rate * annual earnings * discounted productive-years factor`

## Inputs

- Economic input year: {main['economic_input_year']}
- Economic sources: {sources}
- Main discount rate: 3%; sensitivity rates: 0% and 5%.

## Main Result

Total productivity losses associated with premature mortality potentially
attributable to insufficient MSA under the modelled counterfactual were
${main['productivity_loss']:,.0f} for ages 18-64 at a 3% discount rate.
Monte Carlo interval: ${main_mc['productivity_loss_p2_5']:,.0f} to
${main_mc['productivity_loss_p97_5']:,.0f}.

## Limitations

- Economic inputs are treated as fixed; uncertainty reflects the refined HR only.
- This is a productivity valuation, not a healthcare-cost estimate.
- Results should not be described as cost savings caused by MSA.
"""
    OUT_REPORT.write_text(text, encoding="utf-8")


def main() -> None:
    ensure_dirs()
    premature_computed = run_premature_productivity_module()
    if not INPUT_FILE.exists():
        write_template_and_docs()
        write_not_computed_report()
        append_issue_once(
            "Missing official productivity inputs",
            "Productivity losses were not computed because `data/external/us_productivity_inputs_by_age_sex.csv` is missing. A template and manual download instructions were created. Do not populate this file with non-official or undocumented values.",
        )
        print(f"Productivity inputs missing. Wrote {TEMPLATE_FILE.relative_to(PROJECT_ROOT)}")
        print(f"Wrote {DOC_FILE.relative_to(PROJECT_ROOT)}")
        print(f"Wrote {OUT_REPORT.relative_to(PROJECT_ROOT)}")
        if not premature_computed:
            print(f"Premature 30-69 productivity losses were not computed; see {OUT_REPORT_PREMATURE.relative_to(PROJECT_ROOT)}")
        return

    productivity = load_productivity_inputs()
    attr, deaths, paf = load_burden_inputs()
    totals, mc, detail = compute_losses(productivity, attr, deaths, paf)
    totals.to_csv(OUT_TOTAL, index=False)
    mc.to_csv(OUT_MC, index=False)
    detail.to_csv(OUT_BY_AGE_SEX, index=False)
    write_computed_report(totals, mc, productivity)
    print(f"Wrote {OUT_TOTAL.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {OUT_MC.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {OUT_BY_AGE_SEX.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {OUT_REPORT.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
