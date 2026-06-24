"""
Figure 2 (new): Panel A survival/cumulative-mortality curves observed vs
counterfactual by sex; Panel B attributable-deaths decomposition by age x sex.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
LT_PATH = BASE / "outputs" / "tables" / "msa_life_table_observed_counterfactual_premature_30_69_nhis2024.csv"
DEC_PATH = BASE / "outputs" / "tables" / "msa_burden_contributions_by_age_sex_premature_30_69.csv"
OUT_DIR = BASE / "outputs" / "figures" / "manuscript"
OUT_DIR.mkdir(parents=True, exist_ok=True)

COLORS = {"Female": "#A6192E", "Male": "#1F4E79"}
SCEN_LS = {"observed": "-", "counterfactual": "--"}
AGE_GROUPS = ["30-34", "35-44", "45-54", "55-64", "65-69"]


def build_cum_mortality(df: pd.DataFrame, sex: str, scenario: str):
    sub = (df[(df["sex"] == sex) & (df["scenario"] == scenario)]
           .sort_values("age_start").reset_index(drop=True))
    ages = [sub["age_start"].iloc[0]]
    lx_at = [sub["lx"].iloc[0]]
    for _, row in sub.iterrows():
        ages.append(row["age_end"])
        lx_at.append(row["lx_next"])
    p_death_pct = [100.0 * (1 - lx / 100000.0) for lx in lx_at]
    return ages, p_death_pct


def main():
    lt = pd.read_csv(LT_PATH)
    dec = pd.read_csv(DEC_PATH)

    fig, (axA, axB) = plt.subplots(
        2, 1, figsize=(7.2, 8.6),
        gridspec_kw={"height_ratios": [1.0, 1.0]}
    )

    # Panel A
    for sex in ("Female", "Male"):
        for scen in ("observed", "counterfactual"):
            ages, p_death = build_cum_mortality(lt, sex, scen)
            label = f"{'Women' if sex == 'Female' else 'Men'} ({scen})"
            axA.plot(
                ages, p_death,
                color=COLORS[sex], linestyle=SCEN_LS[scen],
                marker="o", markersize=4.5, linewidth=1.8, label=label,
            )
    axA.set_xlabel("Age (years)", fontsize=10.5)
    axA.set_ylabel("Cumulative probability of death\nsince age 30 (%)", fontsize=10.5)
    axA.set_xticks([30, 35, 45, 55, 65, 70])
    axA.set_xlim(29, 71)
    axA.set_ylim(bottom=0)
    axA.grid(True, linestyle=":", alpha=0.4)
    axA.legend(loc="upper left", fontsize=8.6, frameon=True, ncol=2)
    axA.text(-0.085, 1.0, "A", transform=axA.transAxes,
             fontsize=14, fontweight="bold", va="top", ha="left")

    # Panel B
    x = np.arange(len(AGE_GROUPS))
    width = 0.38

    f_central, f_lo, f_hi = [], [], []
    m_central, m_lo, m_hi = [], [], []
    for ag in AGE_GROUPS:
        fr = dec[(dec["age_group"] == ag) & (dec["sex"] == "Female")].iloc[0]
        mr = dec[(dec["age_group"] == ag) & (dec["sex"] == "Male")].iloc[0]
        f_central.append(fr["attributable_deaths"] / 1000)
        f_lo.append((fr["attributable_deaths"] - fr["attributable_deaths_p2_5"]) / 1000)
        f_hi.append((fr["attributable_deaths_p97_5"] - fr["attributable_deaths"]) / 1000)
        m_central.append(mr["attributable_deaths"] / 1000)
        m_lo.append((mr["attributable_deaths"] - mr["attributable_deaths_p2_5"]) / 1000)
        m_hi.append((mr["attributable_deaths_p97_5"] - mr["attributable_deaths"]) / 1000)

    axB.bar(x - width / 2, f_central, width,
            yerr=[f_lo, f_hi], color=COLORS["Female"], alpha=0.85,
            edgecolor="white", capsize=3, label="Women")
    axB.bar(x + width / 2, m_central, width,
            yerr=[m_lo, m_hi], color=COLORS["Male"], alpha=0.85,
            edgecolor="white", capsize=3, label="Men")

    axB.set_xlabel("Age group (years)", fontsize=10.5)
    axB.set_ylabel("Potentially attributable deaths\n(thousands)", fontsize=10.5)
    axB.set_xticks(x)
    axB.set_xticklabels(AGE_GROUPS)
    axB.set_ylim(bottom=0)
    axB.grid(True, axis="y", linestyle=":", alpha=0.4)
    axB.legend(loc="upper left", fontsize=8.6, frameon=True)
    axB.text(-0.085, 1.0, "B", transform=axB.transAxes,
             fontsize=14, fontweight="bold", va="top", ha="left")

    plt.tight_layout()
    pdf_path = OUT_DIR / "figure2_survival_decomposition.pdf"
    png_path = OUT_DIR / "figure2_survival_decomposition.png"
    fig.savefig(pdf_path, bbox_inches="tight")
    fig.savefig(png_path, bbox_inches="tight", dpi=200)
    plt.close(fig)
    print(f"Wrote {pdf_path}")
    print(f"Wrote {png_path}")


if __name__ == "__main__":
    main()
