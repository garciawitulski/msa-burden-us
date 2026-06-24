source(file.path("code", "r", "lib", "msaburden.R"))

ensure_standard_dirs()
table_dir <- here("outputs", "tables")
out <- here("outputs", "tables", "manuscript", "derived_subtotals_for_results.csv")
rows <- list()

contrib <- if (file.exists(file.path(table_dir, "msa_burden_contributions_by_age_sex_premature_30_69.csv"))) read.csv(file.path(table_dir, "msa_burden_contributions_by_age_sex_premature_30_69.csv"), stringsAsFactors = FALSE, check.names = FALSE) else data.frame()
if (nrow(contrib)) {
  rows[[length(rows) + 1]] <- data.frame(metric = "attributable_deaths_total", value = sum(num(contrib$attributable_deaths), na.rm = TRUE), source = "msa_burden_contributions_by_age_sex_premature_30_69.csv")
  rows[[length(rows) + 1]] <- data.frame(metric = "yll_total", value = sum(num(contrib$yll), na.rm = TRUE), source = "msa_burden_contributions_by_age_sex_premature_30_69.csv")
}
prod <- if (file.exists(file.path(table_dir, "msa_productivity_losses_premature_30_69_nhis2024.csv"))) read.csv(file.path(table_dir, "msa_productivity_losses_premature_30_69_nhis2024.csv"), stringsAsFactors = FALSE, check.names = FALSE) else data.frame()
if (nrow(prod)) {
  main <- prod[prod$earnings_measure == "pernp_mean" & prod$productive_horizon == 65 & num(prod$discount_rate) == 0.03, ][1, ]
  rows[[length(rows) + 1]] <- data.frame(metric = "productivity_loss_main", value = num(main$productivity_loss), source = "msa_productivity_losses_premature_30_69_nhis2024.csv")
}
if (length(rows)) write_csv(do.call(rbind, rows), out) else write_csv(data.frame(metric = character(), value = numeric(), source = character()), out)
message("Derived subtotals written.")
