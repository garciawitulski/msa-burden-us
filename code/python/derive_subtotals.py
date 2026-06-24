"""Compute the subtotals and aggregations needed for the manuscript tables and Results expansion.

This script reads only existing CSV outputs and produces:
  - Sex subtotals and grand totals for attributable deaths and YLL (Table 4)
  - Productivity-loss subtotals by age, by sex, and total under PERNP, horizon=65, discount=3%
  - PAF lower/upper bounds derived from HR CI bounds 1.036 and 1.108 applied stratum-by-stratum
  - Pooled-by-age prevalence of insufficient MSA (both sexes) for the Results paragraph 2

It writes a single audit CSV at outputs/tables/manuscript/derived_subtotals_for_results.csv
so all derivations are inspectable.
"""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TABLES = ROOT / "outputs" / "tables"
OUT = TABLES / "manuscript" / "derived_subtotals_for_results.csv"


def read_csv(p: Path) -> list[dict]:
    with p.open() as fh:
        return list(csv.DictReader(fh))


def main() -> None:
    rows: list[dict] = []

    # --- Table 4: sex subtotals and grand totals ---
    t4 = read_csv(TABLES / "msa_burden_contributions_by_age_sex_premature_30_69.csv")
    sex_deaths = {"Female": 0.0, "Male": 0.0}
    sex_yll = {"Female": 0.0, "Male": 0.0}
    sex_allcause = {"Female": 0.0, "Male": 0.0}
    for r in t4:
        s = r["sex"]
        sex_deaths[s] += float(r["attributable_deaths"])
        sex_yll[s] += float(r["yll"])
        sex_allcause[s] += float(r["deaths_allcause"])
    total_deaths = sum(sex_deaths.values())
    total_yll = sum(sex_yll.values())
    for s in ("Female", "Male"):
        rows.append(
            {
                "metric": "attributable_deaths",
                "stratum": f"sex={s}",
                "value": round(sex_deaths[s]),
                "share_of_total_percent": round(100 * sex_deaths[s] / total_deaths, 1),
                "source": "sum over age groups in msa_burden_contributions_by_age_sex_premature_30_69.csv",
            }
        )
        rows.append(
            {
                "metric": "yll",
                "stratum": f"sex={s}",
                "value": round(sex_yll[s]),
                "share_of_total_percent": round(100 * sex_yll[s] / total_yll, 1),
                "source": "sum over age groups in msa_burden_contributions_by_age_sex_premature_30_69.csv",
            }
        )
    rows.append(
        {
            "metric": "attributable_deaths",
            "stratum": "total",
            "value": round(total_deaths),
            "share_of_total_percent": 100.0,
            "source": "sum over Female+Male",
        }
    )
    rows.append(
        {
            "metric": "yll",
            "stratum": "total",
            "value": round(total_yll),
            "share_of_total_percent": 100.0,
            "source": "sum over Female+Male",
        }
    )

    # --- Productivity by age and by sex under PERNP, horizon=65, rate=0.03 ---
    prod = read_csv(TABLES / "msa_productivity_losses_by_age_sex_premature_30_69_nhis2024.csv")
    age_prod = {}
    sex_prod = {"Female": 0.0, "Male": 0.0}
    total_prod = 0.0
    for r in prod:
        if r["earnings_measure"] != "pernp_mean":
            continue
        if int(r["productive_horizon"]) != 65:
            continue
        if abs(float(r["discount_rate"]) - 0.03) > 1e-9:
            continue
        v = float(r["productivity_loss"])
        age_prod[r["age_group"]] = age_prod.get(r["age_group"], 0.0) + v
        sex_prod[r["sex"]] += v
        total_prod += v
    for ag, v in sorted(age_prod.items()):
        rows.append(
            {
                "metric": "productivity_loss_pernp65_3pct",
                "stratum": f"age_group={ag}",
                "value": int(round(v)),
                "share_of_total_percent": round(100 * v / total_prod, 1),
                "source": "sum F+M, msa_productivity_losses_by_age_sex_premature_30_69_nhis2024.csv (PERNP, horizon=65, r=3%)",
            }
        )
    for s in ("Female", "Male"):
        rows.append(
            {
                "metric": "productivity_loss_pernp65_3pct",
                "stratum": f"sex={s}",
                "value": int(round(sex_prod[s])),
                "share_of_total_percent": round(100 * sex_prod[s] / total_prod, 1),
                "source": "sum over ages, PERNP/65/3%",
            }
        )
    rows.append(
        {
            "metric": "productivity_loss_pernp65_3pct",
            "stratum": "total",
            "value": int(round(total_prod)),
            "share_of_total_percent": 100.0,
            "source": "sum over all strata",
        }
    )

    # --- PAF lower/upper bounds for Figure 2 panel B and tables (HR CI 1.036 / 1.108) ---
    t3 = read_csv(TABLES / "manuscript" / "table3_nhis2024_prevalence_paf.csv")
    HR_LO, HR_HI = 1.036, 1.108
    for r in t3:
        # Reconstruct prevalence (decimal) from the table's percent column
        p = float(r["insufficient_MSA_percent"]) / 100
        for hr, lab in ((HR_LO, "lo"), (HR_HI, "hi")):
            paf = (p * (hr - 1)) / (1 + p * (hr - 1)) * 100
            rows.append(
                {
                    "metric": "paf_percent_bound",
                    "stratum": f"age={r['age_group']},sex={r['sex']},bound={lab}",
                    "value": round(paf, 2),
                    "share_of_total_percent": "",
                    "source": f"PAF formula with HR={hr}, p={p:.4f} from table3",
                }
            )

    # --- Pooled-by-age prevalence (both sexes) for Results paragraph 2 ---
    by_age = TABLES / "nhis_2024_msa_prevalence_premature_30_69_by_age.csv"
    if by_age.exists():
        for r in read_csv(by_age):
            ag = r.get("age_group") or r.get("group_value") or ""
            ins = r.get("prevalence_insufficient_msa")
            if ins:
                rows.append(
                    {
                        "metric": "prevalence_insufficient_pooled_by_age",
                        "stratum": f"age={ag}",
                        "value": round(float(ins) * 100, 1),
                        "share_of_total_percent": "",
                        "source": "nhis_2024_msa_prevalence_premature_30_69_by_age.csv",
                    }
                )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["metric", "stratum", "value", "share_of_total_percent", "source"])
        w.writeheader()
        for row in rows:
            w.writerow(row)
    print(f"wrote {OUT}")
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
