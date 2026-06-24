source(file.path("code", "r", "lib", "msaburden.R"))

ensure_standard_dirs()
table_dir <- here("outputs", "tables")
manuscript_dir <- file.path(table_dir, "manuscript")
supp_dir <- here("manuscript_latex", "supplement", "tables")
ensure_dir(supp_dir)

longtable <- function(caption, label, df, note = "") {
  headers <- paste0("\\textbf{", names(df), "}", collapse = " & ")
  rows <- apply(df, 1, function(x) paste(as.character(x), collapse = " & "))
  paste(c(
    "\\begingroup",
    "\\scriptsize",
    paste0("\\begin{longtable}{", paste(rep("l", ncol(df)), collapse = ""), "}"),
    paste0("\\caption{", caption, "}\\label{", label, "}\\\\"),
    "\\toprule",
    paste0(headers, " \\\\"),
    "\\midrule",
    paste0(rows, " \\\\"),
    "\\bottomrule",
    "\\end{longtable}",
    paste0("{\\footnotesize \\emph{Notes:} ", note, "\\par}"),
    "\\endgroup"
  ), collapse = "\n")
}

write_lt <- function(input, output, caption, label, note = "") {
  if (!file.exists(input)) {
    append_issue_once("Supplement input missing", paste0("Missing `", rel_path(input), "` for supplement table `", output, "`."))
    return(invisible(FALSE))
  }
  df <- read.csv(input, stringsAsFactors = FALSE, check.names = FALSE)
  write_text(file.path(supp_dir, output), longtable(caption, label, df, note))
  invisible(TRUE)
}

write_lt(file.path(table_dir, "hr_inputs_for_burden.csv"), "supp_table_s05_hr_inputs.tex", "Hazard ratio inputs used in burden estimation.", "tab:s-hr-inputs", "HR = hazard ratio; MSA = muscle-strengthening activity.")
write_lt(file.path(manuscript_dir, "table3_nhis2024_prevalence_paf.csv"), "supp_table_s06_prevalence_paf.tex", "Prevalence of insufficient MSA and PAF by age and sex, NHIS 2024.", "tab:s-prevalence-paf", "PAF = population attributable fraction.")
write_lt(file.path(manuscript_dir, "table4_attributable_deaths_yll.csv"), "supp_table_s07_deaths_yll.tex", "Potentially attributable deaths and YLL by age and sex.", "tab:s-deaths-yll", "YLL = years of life lost.")
write_lt(file.path(table_dir, "msa_life_expectancy_gain_premature_30_69_nhis2024.csv"), "supp_table_s08_life_expectancy_gains.tex", "Life expectancy gains between ages 30 and 70.", "tab:s-life-expectancy-gains", "Broad-group approximation.")
write_lt(file.path(table_dir, "msa_productivity_losses_premature_30_69_nhis2024.csv"), "supp_table_s09_productivity_sensitivity.tex", "Productivity-loss assumptions and sensitivity analyses.", "tab:s-productivity-sensitivity", "Productivity valuation, not healthcare costs.")

prod_path <- file.path(table_dir, "msa_productivity_losses_premature_30_69_nhis2024.csv")
if (file.exists(prod_path)) {
  prod <- read.csv(prod_path, stringsAsFactors = FALSE, check.names = FALSE)
  main <- prod[prod$earnings_measure == "pernp_mean" & prod$productive_horizon == 65 & num(prod$discount_rate) == 0.03, ][1, ]
  loss <- num(main$productivity_loss)
  gdp <- 29298013000000
  gdp_df <- data.frame(quantity = c("Productivity losses", "U.S. nominal GDP, annual 2024", "Share of GDP"), value = c(fmt_money(loss), "US\\$29,298.013 billion", paste0(fmt_float(loss / gdp * 100, 6), "\\%")))
  write_text(file.path(supp_dir, "supp_table_s10_gdp_context.tex"), longtable("Productivity losses as a share of U.S. GDP.", "tab:s-gdp-context", gdp_df, "GDP = gross domestic product."))
}
message("Created supplement appendix tables.")
