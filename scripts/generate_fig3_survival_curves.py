"""
Figure 3: Cumulative all-cause mortality between ages 30 and 70 under observed
mortality and the modeled counterfactual, by sex (Panel A: Women, Panel B: Men).
The shaded region between the curves represents the potential reduction under
the counterfactual that adults with insufficient MSA meet the guideline threshold.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
LT_PATH = BASE / "outputs" / "tables" / "msa_life_table_observed_counterfactual_premature_30_69_nhis2024.csv"
OUT_DIR = BASE / "outputs" / "figures" / "manuscript"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Lancet-style palette
COLOR_F = "#A6192E"
COLOR_M = "#1F4E79"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 10,
    "axes.labelsize": 10.5,
    "axes.titlesize": 11.5,
    "xtick.labelsize": 9.5,
    "ytick.labelsize": 9.5,
    "legend.fontsize": 9,
    "axes.linewidth": 0.9,
    "xtick.major.width": 0.9,
    "ytick.major.width": 0.9,
    "xtick.direction": "out",
    "ytick.direction": "out",
})


def build_cum_mortality(df: pd.DataFrame, sex: str, scenario: str):
    sub = (df[(df["sex"] == sex) & (df["scenario"] == scenario)]
           .sort_values("age_start").reset_index(drop=True))
    ages = [sub["age_start"].iloc[0]]
    lx_at = [sub["lx"].iloc[0]]
    for _, row in sub.iterrows():
        ages.append(row["age_end"])
        lx_at.append(row["lx_next"])
    return ages, [100.0 * (1 - lx / 100000.0) for lx in lx_at]


def style_axis(ax, panel_letter, title, color):
    ax.text(-0.13, 1.04, panel_letter, transform=ax.transAxes,
            fontsize=14, fontweight="bold", va="top", ha="left")
    ax.set_title(title, fontsize=11.5, color=color, fontweight="bold", pad=10)
    ax.set_xticks([30, 35, 45, 55, 65, 70])
    ax.set_xlim(29.2, 76.5)
    ax.grid(True, linestyle=":", linewidth=0.6, alpha=0.55, color="0.5")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("0.3")


def add_stat_callout(ax, ages, p_obs, p_cf, color):
    """Single boxed callout summarising the gap at age 70, with leader line."""
    x = ages[-1]
    y_obs, y_cf = p_obs[-1], p_cf[-1]
    delta = y_obs - y_cf
    midpoint = (y_obs + y_cf) / 2

    text = (
        f"$\\bf{{At\\ age\\ 70}}$\n"
        f"Observed:        {y_obs:.2f}%\n"
        f"Counterfactual: {y_cf:.2f}%\n"
        f"$\\Delta$ = {delta:.2f} pp\n"
        f"≈ {delta * 1000:.0f} deaths averted\n"
        f"per 100,000"
    )
    ax.annotate(
        text,
        xy=(x, midpoint),
        xytext=(40, 24),
        fontsize=8.4, color="0.12", ha="left", va="top",
        bbox=dict(boxstyle="round,pad=0.55", fc="white",
                  ec=color, alpha=0.97, lw=0.9),
        arrowprops=dict(arrowstyle="->", color="0.45", lw=0.9,
                        connectionstyle="arc3,rad=-0.18",
                        shrinkA=0, shrinkB=4),
    )


def main():
    lt = pd.read_csv(LT_PATH)

    fig, axes = plt.subplots(1, 2, figsize=(9.0, 4.2), sharey=True)
    fig.subplots_adjust(wspace=0.12)

    for ax, sex, label, panel_letter, color in [
        (axes[0], "Female", "Women", "A", COLOR_F),
        (axes[1], "Male", "Men", "B", COLOR_M),
    ]:
        ages_obs, p_obs = build_cum_mortality(lt, sex, "observed")
        ages_cf, p_cf = build_cum_mortality(lt, sex, "counterfactual")

        ax.fill_between(ages_obs, p_obs, p_cf,
                        color=color, alpha=0.18, linewidth=0,
                        label="Potential reduction")
        ax.plot(ages_obs, p_obs, color=color, linestyle="-", linewidth=2.2,
                marker="o", markersize=5.5, label="Observed", zorder=3,
                solid_capstyle="round")
        ax.plot(ages_cf, p_cf, color=color, linestyle="--", linewidth=1.8,
                marker="s", markersize=4.5, label="Counterfactual", zorder=3,
                markerfacecolor="white", markeredgecolor=color, markeredgewidth=1.4,
                dash_capstyle="round")

        style_axis(ax, panel_letter, label, color)
        ax.set_xlabel("Age (years)")
        ax.set_ylim(0, 27)
        annotate_endpoints(ax, ages_obs, p_obs, p_cf, color)

        legend = ax.legend(loc="upper left", frameon=True, fancybox=False,
                           framealpha=0.97, edgecolor="0.7", borderpad=0.6,
                           handlelength=2.2, labelspacing=0.45)
        legend.get_frame().set_linewidth(0.7)

    axes[0].set_ylabel("Cumulative probability of death since age 30 (%)")

    pdf_path = OUT_DIR / "figure3_survival_curves.pdf"
    png_path = OUT_DIR / "figure3_survival_curves.png"
    fig.savefig(pdf_path, bbox_inches="tight")
    fig.savefig(png_path, bbox_inches="tight", dpi=220)
    plt.close(fig)
    print(f"Wrote {pdf_path}")
    print(f"Wrote {png_path}")


if __name__ == "__main__":
    main()
