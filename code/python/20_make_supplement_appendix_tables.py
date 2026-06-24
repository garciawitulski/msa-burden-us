"""Generate LaTeX tables for the active Supplementary Appendix.

The main manuscript tables are produced elsewhere. This script bridges those
validated CSV/Markdown outputs into the standalone appendix table files.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TABLE_DIR = PROJECT_ROOT / "outputs" / "tables"
MANUSCRIPT_TABLE_DIR = TABLE_DIR / "manuscript"
SUPP_TABLE_DIR = PROJECT_ROOT / "manuscript_latex" / "supplement" / "tables"

HR_INPUTS = TABLE_DIR / "hr_inputs_for_burden.csv"
TABLE3 = MANUSCRIPT_TABLE_DIR / "table3_nhis2024_prevalence_paf.csv"
TABLE4 = MANUSCRIPT_TABLE_DIR / "table4_attributable_deaths_yll.csv"
LIFE = TABLE_DIR / "msa_life_expectancy_gain_premature_30_69_nhis2024.csv"
LIFE_MC = TABLE_DIR / "msa_life_expectancy_gain_montecarlo_premature_30_69_nhis2024.csv"
PRODUCTIVITY = TABLE_DIR / "msa_productivity_losses_premature_30_69_nhis2024.csv"
PRODUCTIVITY_MC = TABLE_DIR / "msa_productivity_losses_montecarlo_premature_30_69_nhis2024.csv"

GDP_2024_USD = 29_298_013_000_000


def read_required(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"Missing required input: {path.relative_to(PROJECT_ROOT)}")
    return pd.read_csv(path)


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")
    print(f"Wrote {path.relative_to(PROJECT_ROOT)}")


def age_tex(value: str) -> str:
    return str(value).replace("-", "--")


def fmt_int(value: float | int | str) -> str:
    if isinstance(value, str):
        value = value.replace(",", "")
    return f"{float(value):,.0f}"


def fmt_float(value: float | int | str, digits: int = 2) -> str:
    return f"{float(value):.{digits}f}"


def fmt_money(value: float | int | str) -> str:
    return r"US\$" + fmt_int(value)


def fmt_ui_text(value: str) -> str:
    return str(value).replace("-", "--")


def longtable(
    caption: str,
    label: str,
    colspec: str,
    headers: list[str],
    rows: list[list[str]],
    *,
    size: str = r"\scriptsize",
    tabcolsep: int = 3,
    note: str = "",
) -> str:
    header_line = " & ".join(rf"\textbf{{{h}}}" for h in headers) + r" \\"
    row_lines = [" & ".join(row) + r" \\" for row in rows]
    body = "\n".join(row_lines)
    return "\n".join(
        [
            r"\begingroup",
            size,
            r"\singlespacing",
            rf"\setlength{{\tabcolsep}}{{{tabcolsep}pt}}",
            r"\renewcommand{\arraystretch}{1.08}",
            rf"\begin{{longtable}}{{@{{}}{colspec}@{{}}}}",
            rf"\caption{{{caption}}}\label{{{label}}}\\",
            r"\toprule",
            header_line,
            r"\midrule",
            r"\endfirsthead",
            rf"\caption[]{{{caption} (continued)}}\\",
            r"\toprule",
            header_line,
            r"\midrule",
            r"\endhead",
            r"\midrule",
            rf"\multicolumn{{{len(headers)}}}{{r}}{{Continued on next page}}\\",
            r"\endfoot",
            r"\bottomrule",
            r"\endlastfoot",
            body,
            r"\end{longtable}",
            r"\par\vspace{-0.5\baselineskip}",
            rf"{{\footnotesize \emph{{Notes:}} {note}\par}}",
            r"\endgroup",
            "",
        ]
    )


def make_s05_hr_inputs() -> None:
    hr = read_required(HR_INPUTS).set_index("scenario")
    labels = {
        "main_hr_target_30_69": (
            "Primary target-population Cox model",
            "Primary burden input",
            "Baseline adults aged 30--69 years, censored at age 70; Taylor-linearized design SEs.",
        ),
        "lag24_hr_target_30_69": (
            "24-month lagged target-population sensitivity",
            "Reverse-causation sensitivity",
            "Same target population; excludes deaths in the first 24 months of follow-up.",
        ),
        "main_hr_adult_refined": (
            "All-adult refined comparison",
            "Comparison sensitivity only",
            "Original adult 18+ refined model retained for comparison; not the primary premature 30--69 input.",
        ),
        "lag24_hr_adult_refined": (
            "24-month lagged all-adult refined comparison",
            "Comparison sensitivity only",
            "Original adult 18+ lagged model retained for comparison; not the primary premature 30--69 input.",
        ),
    }
    rows = []
    for scenario, (analysis, role, detail) in labels.items():
        row = hr.loc[scenario]
        rows.append(
            [
                analysis,
                "Insufficient MSA versus meeting the guideline threshold",
                fmt_float(row["hr"], 3),
                f"{fmt_float(row['ci_lower'], 3)}--{fmt_float(row['ci_upper'], 3)}",
                role,
                detail,
            ]
        )
    text = longtable(
        "Hazard ratio inputs used in burden estimation.",
        "tab:s-hr-inputs",
        r"p{0.18\linewidth}p{0.19\linewidth}p{0.08\linewidth}p{0.12\linewidth}p{0.15\linewidth}p{0.22\linewidth}",
        ["Analysis", "Exposure contrast", "HR", "95\\% CI", "Analytic role", "Details"],
        rows,
        size=r"\scriptsize",
        tabcolsep=3,
        note=(
            "The main premature 30--69 burden analysis uses the reviewer-response "
            "target-population HR for insufficient MSA. Adult refined HRs are retained "
            "only as comparison sensitivities. CI = confidence interval; HR = hazard "
            "ratio; MSA = muscle-strengthening activity; SE = standard error."
        ),
    )
    write_text(SUPP_TABLE_DIR / "supp_table_s05_hr_inputs.tex", text)


def make_s06_prevalence_paf() -> None:
    t3 = read_required(TABLE3)
    rows = []
    for _, row in t3.iterrows():
        rows.append(
            [
                age_tex(row["age_group"]),
                row["sex"],
                str(row["n_unweighted"]),
                fmt_float(row["meeting_MSA_guideline_percent"], 1),
                fmt_float(row["insufficient_MSA_percent"], 1),
                fmt_float(row["PAF_percent"], 2),
            ]
        )
    text = longtable(
        "Prevalence of insufficient MSA and PAF by age and sex, NHIS 2024.",
        "tab:s-prevalence-paf",
        r"p{0.12\linewidth}p{0.12\linewidth}r r r r",
        ["Age group", "Sex", "n", "Meeting threshold (\\%)", "Insufficient MSA (\\%)", "PAF (\\%)"],
        rows,
        size=r"\scriptsize",
        tabcolsep=4,
        note=(
            "Prevalence estimates use NHIS 2024 sample-adult survey weights among adults aged "
            "30--69 years. PAFs use the reviewer-response target-population mortality HR and "
            "age-sex-specific prevalence. MSA = muscle-strengthening activity; PAF = population "
            "attributable fraction."
        ),
    )
    write_text(SUPP_TABLE_DIR / "supp_table_s06_prevalence_paf.tex", text)


def make_s07_deaths_yll() -> None:
    t4 = read_required(TABLE4)
    rows = []
    for _, row in t4.iterrows():
        rows.append(
            [
                age_tex(row["age_group"]),
                row["sex"],
                str(row["all_cause_deaths"]),
                fmt_float(row["PAF_percent"], 2),
                fmt_ui_text(row["attributable_deaths_95_UI"]),
                fmt_ui_text(row["YLL_95_UI"]),
                fmt_float(row["share_attributable_deaths_percent"], 1),
                fmt_float(row["share_YLL_percent"], 1),
                fmt_float(row["remaining_life_expectancy"], 1),
            ]
        )
    body = "\n".join(" & ".join(row) + r" \\" for row in rows)
    text = "\n".join(
        [
            r"\begin{landscape}",
            r"\begin{table}[htbp]",
            r"\centering",
            r"\scriptsize",
            r"\setlength{\tabcolsep}{3pt}",
            r"\renewcommand{\arraystretch}{1.08}",
            r"\caption{Potentially attributable deaths and YLL by age and sex.}\label{tab:s-deaths-yll}",
            r"\resizebox{0.98\linewidth}{!}{%",
            r"\begin{tabular}{@{}llrrrrrrr@{}}",
            r"\toprule",
            r"\textbf{Age group} & \textbf{Sex} & \textbf{All-cause deaths} & \textbf{PAF (\%)} & \textbf{Potentially attributable deaths (95\% UI)} & \textbf{YLL (95\% UI)} & \textbf{Deaths share (\%)} & \textbf{YLL share (\%)} & \textbf{Remaining LE} \\",
            r"\midrule",
            body,
            r"\bottomrule",
            r"\end{tabular}%",
            r"}",
            r"\par\vspace{4pt}",
            r"\begin{minipage}{0.95\linewidth}",
            r"\footnotesize \emph{Notes:} All-cause deaths are deaths occurring between ages 30 and 69 years in 2024. Uncertainty intervals propagate uncertainty in the target-population HR only. Remaining LE refers to remaining life expectancy at the representative age for the age group. HR = hazard ratio; LE = life expectancy; PAF = population attributable fraction; UI = uncertainty interval; YLL = years of life lost.",
            r"\end{minipage}",
            r"\end{table}",
            r"\end{landscape}",
            "",
        ]
    )
    write_text(SUPP_TABLE_DIR / "supp_table_s07_deaths_yll.tex", text)


def make_s08_life_expectancy() -> None:
    life = read_required(LIFE)
    mc = read_required(LIFE_MC)
    merged = life.merge(mc, on="sex", how="left")
    order = ["Female", "Male", "All"]
    rows = []
    for sex in order:
        row = merged.loc[merged["sex"] == sex].iloc[0]
        lo = max(float(row["gain_temporary_life_expectancy_30_70_p2_5"]), 0.0)
        hi = float(row["gain_temporary_life_expectancy_30_70_p97_5"])
        rows.append(
            [
                sex,
                fmt_float(float(row["observed_probability_death_30_70"]) * 100, 2),
                fmt_float(float(row["counterfactual_probability_death_30_70"]) * 100, 2),
                fmt_float(row["observed_temporary_life_expectancy_30_70"], 3),
                fmt_float(row["counterfactual_temporary_life_expectancy_30_70"], 3),
                f"{fmt_float(row['gain_temporary_life_expectancy_30_70'], 3)} ({fmt_float(lo, 3)}--{fmt_float(hi, 3)})",
            ]
        )
    text = longtable(
        "Life expectancy gains between ages 30 and 70.",
        "tab:s-life-expectancy-gains",
        r"p{0.10\linewidth}>{\raggedleft\arraybackslash}p{0.17\linewidth}>{\raggedleft\arraybackslash}p{0.19\linewidth}>{\raggedleft\arraybackslash}p{0.13\linewidth}>{\raggedleft\arraybackslash}p{0.15\linewidth}>{\raggedleft\arraybackslash}p{0.18\linewidth}",
        [
            "Sex",
            "Observed death probability (\\%)",
            "Counterfactual death probability (\\%)",
            "Observed years",
            "Counterfactual years",
            "Gain (95\\% UI), years",
        ],
        rows,
        size=r"\scriptsize",
        tabcolsep=3,
        note=(
            "Estimates describe life expectancy gains between ages 30 and 70 under the modelled "
            "counterfactual. The calculation uses broad age groups and counterfactual mortality "
            "rates after applying age- and sex-specific PAF reductions to observed mortality rates. "
            "Lower uncertainty limits that were slightly below zero because the HR confidence "
            "interval was close to the null are displayed as 0.000. HR = hazard ratio; PAF = "
            "population attributable fraction; UI = uncertainty interval."
        ),
    )
    write_text(SUPP_TABLE_DIR / "supp_table_s08_life_expectancy_gains.tex", text)


def make_s09_productivity() -> None:
    prod = read_required(PRODUCTIVITY)
    mc = read_required(PRODUCTIVITY_MC)
    merged = prod.merge(
        mc,
        on=["analysis", "earnings_measure", "productive_horizon", "discount_rate"],
        how="left",
    )
    measure_labels = {
        "pernp_mean": "Personal earnings",
        "wagp_mean": "Wage or salary earnings",
    }
    rows = []
    for measure in ["pernp_mean", "wagp_mean"]:
        for horizon in [65, 70, 75]:
            for discount in [0.0, 0.03, 0.05]:
                row = merged[
                    (merged["earnings_measure"] == measure)
                    & (merged["productive_horizon"] == horizon)
                    & (abs(merged["discount_rate"] - discount) < 1e-9)
                ].iloc[0]
                lo = max(float(row["productivity_loss_p2_5"]), 0.0)
                hi = float(row["productivity_loss_p97_5"])
                ui = (
                    f"{fmt_money(row['productivity_loss_median'])} "
                    f"({fmt_money(lo)}--{fmt_money(hi)})"
                )
                rows.append(
                    [
                        measure_labels[measure],
                        str(horizon),
                        fmt_float(discount * 100, 0),
                        fmt_money(row["productivity_loss"]),
                        ui,
                    ]
                )
    text = longtable(
        "Productivity-loss assumptions and sensitivity analyses.",
        "tab:s-productivity-sensitivity",
        r"p{0.18\linewidth}r r p{0.22\linewidth}p{0.30\linewidth}",
        ["Earnings measure", "Productive horizon", "Discount rate (\\%)", "Productivity losses", "Productivity losses (95\\% UI)"],
        rows,
        size=r"\scriptsize",
        tabcolsep=3,
        note=(
            "All rows use deaths occurring between ages 30 and 69 years and the target-population "
            "mortality HR. The main specification uses personal earnings, a productive horizon "
            "through age 65, and 3\\% annual discounting. Lower uncertainty limits are bounded "
            "at zero for productivity-loss reporting. HR = hazard ratio; UI = uncertainty interval."
        ),
    )
    write_text(SUPP_TABLE_DIR / "supp_table_s09_productivity_sensitivity.tex", text)


def make_s10_gdp_context() -> None:
    prod = read_required(PRODUCTIVITY)
    main = prod[
        (prod["earnings_measure"] == "pernp_mean")
        & (prod["productive_horizon"] == 65)
        & (abs(prod["discount_rate"] - 0.03) < 1e-9)
    ].iloc[0]
    loss = float(main["productivity_loss"])
    share = loss / GDP_2024_USD * 100
    loss_latex = fmt_int(loss).replace(",", "{,}")
    rows = [
        ["Productivity losses from premature mortality", fmt_money(loss)],
        ["U.S. nominal GDP, annual 2024", r"US\$29,298.013 billion"],
        [
            "Calculation",
            rf"\({loss_latex} / 29{{,}}298{{,}}013{{,}}000{{,}}000 \times 100\)",
        ],
        ["Share of U.S. GDP", f"{share:.6f}\\%"],
        ["Rounded value", "0.06\\%"],
        [
            "Source for GDP",
            "U.S. Bureau of Economic Analysis, National Income and Product Accounts, current-dollar GDP, annual 2024; BEA Account Code A191RC.",
        ],
    ]
    text = longtable(
        "Productivity losses as a share of U.S. GDP.",
        "tab:s-gdp-context",
        r"p{0.42\linewidth}p{0.44\linewidth}",
        ["Quantity", "Value"],
        rows,
        size=r"\small",
        tabcolsep=4,
        note=(
            "GDP was used only to contextualise the productivity-loss estimate and was not used "
            "in the primary productivity-loss calculation. GDP = gross domestic product."
        ),
    )
    write_text(SUPP_TABLE_DIR / "supp_table_s10_gdp_context.tex", text)


def main() -> None:
    SUPP_TABLE_DIR.mkdir(parents=True, exist_ok=True)
    make_s05_hr_inputs()
    make_s06_prevalence_paf()
    make_s07_deaths_yll()
    make_s08_life_expectancy()
    make_s09_productivity()
    make_s10_gdp_context()


if __name__ == "__main__":
    main()
