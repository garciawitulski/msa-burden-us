"""Quality checks and descriptive summaries for MSA survival datasets."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "data/processed"
INTERIM_DIR = PROJECT_ROOT / "data/interim"
LOG_DIR = PROJECT_ROOT / "outputs/logs"
TABLE_DIR = PROJECT_ROOT / "outputs/tables"


def ensure_dirs() -> None:
    for path in [LOG_DIR, TABLE_DIR, PROCESSED_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def write_issue(message: str) -> None:
    ensure_dirs()
    path = LOG_DIR / "issues_to_resolve.md"
    old = path.read_text(encoding="utf-8") if path.exists() else "# Issues to Resolve\n\n"
    with path.open("w", encoding="utf-8") as handle:
        handle.write(old.rstrip() + "\n\n")
        handle.write(f"## {datetime.now().isoformat(timespec='seconds')}\n\n")
        handle.write(message.rstrip() + "\n")


def stop(message: str) -> None:
    write_issue(message)
    raise SystemExit(message)


def weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    mask = values.notna() & weights.notna() & (weights > 0)
    if not mask.any():
        return np.nan
    return float(np.average(values.loc[mask], weights=weights.loc[mask]))


def add_metric(rows: list[dict], group: str, group_value: str, metric: str, unweighted: float, weighted: float | None = None) -> None:
    rows.append(
        {
            "group": group,
            "group_value": group_value,
            "metric": metric,
            "unweighted": unweighted,
            "weighted": np.nan if weighted is None else weighted,
        }
    )


def summarize_subset(df: pd.DataFrame, group: str, group_value: str) -> list[dict]:
    rows: list[dict] = []
    weights = pd.to_numeric(df.get("weight_mortality", pd.Series(np.nan, index=df.index)), errors="coerce")
    followup_years = pd.to_numeric(df["followup_time_months"], errors="coerce") / 12
    deaths = pd.to_numeric(df["died_allcause"], errors="coerce")

    add_metric(rows, group, group_value, "total N", float(len(df)), float(weights.sum(skipna=True)))
    add_metric(rows, group, group_value, "deaths", float(deaths.sum(skipna=True)), weighted_mean(deaths, weights) * weights.sum(skipna=True))
    add_metric(rows, group, group_value, "person-years", float(followup_years.sum(skipna=True)), float((followup_years * weights).sum(skipna=True)))
    add_metric(rows, group, group_value, "mean follow-up years", float(followup_years.mean(skipna=True)), weighted_mean(followup_years, weights))

    for var in ["msa_cat5", "msa_guideline", "aerobic_guideline_cat", "combined_guideline"]:
        if var not in df:
            continue
        for level, sub in df.groupby(var, dropna=False):
            if pd.isna(level):
                level_name = "missing"
                indicator = df[var].isna().astype(float)
            else:
                level_name = str(level)
                indicator = (df[var] == level).astype(float)
            add_metric(
                rows,
                group,
                group_value,
                f"prevalence {var}: {level_name}",
                float(indicator.mean(skipna=True)),
                weighted_mean(indicator, weights),
            )
    return rows


def main() -> None:
    ensure_dirs()
    full_path = PROCESSED_DIR / "msa_survival_full.csv"
    if not full_path.exists():
        stop("`data/processed/msa_survival_full.csv` not found. Run 03_build_msa_survival_dataset.py first.")

    df = pd.read_csv(full_path, low_memory=False)

    metadata_path = INTERIM_DIR / "msa_build_metadata.json"
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        pd.DataFrame(metadata.get("sample_flow", [])).to_csv(PROCESSED_DIR / "msa_sample_flow.csv", index=False)
    else:
        write_issue("`data/interim/msa_build_metadata.json` was not found; sample flow cannot include raw respondent counts.")

    missing_rows = []
    for col in df.columns:
        missing_rows.append({"variable": col, "missing_n": int(df[col].isna().sum()), "missing_pct": float(df[col].isna().mean())})
    pd.DataFrame(missing_rows).to_csv(TABLE_DIR / "msa_missingness.csv", index=False)

    rows = summarize_subset(df, "overall", "all")
    if "sex" in df:
        for level, sub in df.groupby("sex", dropna=False):
            rows.extend(summarize_subset(sub, "sex", "missing" if pd.isna(level) else str(level)))
    if "age_cat" in df:
        for level, sub in df.groupby("age_cat", dropna=False):
            rows.extend(summarize_subset(sub, "age_cat", "missing" if pd.isna(level) else str(level)))
    pd.DataFrame(rows).to_csv(PROCESSED_DIR / "msa_descriptive_summary.csv", index=False)

    year_rows = []
    if "survey_year" in df:
        for year, sub in df.groupby("survey_year"):
            reason = "included in full dataset: sample adult age 18+, mortality-linkage eligible, non-missing follow-up"
            if year == 1997:
                reason += "; review 1997 PA quarter coverage before final models"
            year_rows.append({"survey_year": int(year), "n": int(len(sub)), "reason": reason})
    pd.DataFrame(year_rows).to_csv(TABLE_DIR / "msa_year_inclusion.csv", index=False)

    log = [
        f"Quality checks run at: {datetime.now().isoformat(timespec='seconds')}",
        f"Rows in full processed dataset: {len(df)}",
        f"Columns: {len(df.columns)}",
        "Created:",
        "- data/processed/msa_sample_flow.csv",
        "- data/processed/msa_descriptive_summary.csv",
        "- outputs/tables/msa_missingness.csv",
        "- outputs/tables/msa_year_inclusion.csv",
    ]
    (LOG_DIR / "quality_checks_log.txt").write_text("\n".join(log) + "\n", encoding="utf-8")
    print("\n".join(log))


if __name__ == "__main__":
    main()
