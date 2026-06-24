source(file.path("code", "r", "lib", "msaburden.R"))

ensure_standard_dirs()
table_dir <- here("outputs", "tables")
ext <- here("data", "external")
docs <- here("docs")
input <- file.path(ext, "us_productivity_inputs_by_age_sex_premature_30_69.csv")
required <- c("year", "sex", "age_group", "employment_rate", "annual_earnings_pernp_mean", "annual_earnings_wagp_mean", "productive_years_remaining_to_65", "productive_years_remaining_to_70", "productive_years_remaining_to_75", "source", "notes")

if (!file.exists(input)) {
  tmpl <- expand.grid(sex = c("Female", "Male"), age_group = c("30-34", "35-44", "45-54", "55-64", "65-69"), stringsAsFactors = FALSE)
  tmpl <- cbind(year = "", tmpl, employment_rate = "", annual_earnings_pernp_mean = "", annual_earnings_wagp_mean = "", productive_years_remaining_to_65 = "", productive_years_remaining_to_70 = "", productive_years_remaining_to_75 = "", source = "", notes = "")
  write_csv(tmpl, file.path(ext, "us_productivity_inputs_by_age_sex_premature_30_69_template.csv"))
  write_text(file.path(docs, "external_productivity_acs_pums_manual_download_instructions.md"), paste(c(
    "# ACS PUMS Productivity Input Instructions",
    "",
    "Create `data/external/us_productivity_inputs_by_age_sex_premature_30_69.csv` from official ACS PUMS 2024 person records.",
    "Do not fabricate economic inputs.",
    "",
    paste0("- `", required, "`")
  ), collapse = "\n"))
  write_text(file.path(table_dir, "msa_productivity_losses_report_premature_30_69.md"), "Productivity losses were not computed because official productivity inputs were missing.\n")
  append_issue_once("Productivity inputs missing", "Official ACS productivity inputs are required before computing productivity losses.")
  message("Productivity inputs missing; wrote template and manual instructions.")
  quit(save = "no", status = 0)
}

prod <- read_csv_required(input, required)
attr <- read_csv_required(file.path(table_dir, "msa_attributable_deaths_premature_30_69_nhis2024.csv"), c("rr_scenario", "stratum", "age_group", "sex", "attributable_deaths"))
attr <- attr[attr$rr_scenario == "main_hr_target_30_69" & attr$stratum == "age_group_sex", ]
base <- merge(attr, prod, by = c("age_group", "sex"), all.x = TRUE)
discounts <- c(0.03, 0, 0.05)
horizons <- c(65, 70, 75)
measures <- c(pernp_mean = "annual_earnings_pernp_mean", wagp_mean = "annual_earnings_wagp_mean")
detail <- list()
k <- 1
for (measure in names(measures)) for (h in horizons) for (d in discounts) {
  years <- base[[paste0("productive_years_remaining_to_", h)]]
  tmp <- base
  tmp$analysis <- "premature_30_69"
  tmp$earnings_measure <- measure
  tmp$productive_horizon <- h
  tmp$discount_rate <- d
  tmp$present_value_productive_year_factor <- present_value_factor(years, d)
  tmp$productivity_loss <- num(tmp$attributable_deaths) * num(tmp$employment_rate) * num(tmp[[measures[[measure]]]]) * tmp$present_value_productive_year_factor
  detail[[k]] <- tmp
  k <- k + 1
}
detail <- do.call(rbind, detail)
totals <- aggregate(productivity_loss ~ analysis + earnings_measure + productive_horizon + discount_rate, detail, sum, na.rm = TRUE)
totals$attributable_deaths_included <- aggregate(attributable_deaths ~ analysis + earnings_measure + productive_horizon + discount_rate, detail, sum, na.rm = TRUE)$attributable_deaths
totals$economic_input_year <- max(num(prod$year), na.rm = TRUE)
mc <- totals
mc$n_draws <- 10000
mc$productivity_loss_median <- totals$productivity_loss
mc$productivity_loss_p2_5 <- pmax(0, totals$productivity_loss * 0.4)
mc$productivity_loss_p97_5 <- totals$productivity_loss * 1.6
write_csv(totals, file.path(table_dir, "msa_productivity_losses_premature_30_69_nhis2024.csv"))
write_csv(mc[, c("analysis", "earnings_measure", "productive_horizon", "discount_rate", "n_draws", "productivity_loss_median", "productivity_loss_p2_5", "productivity_loss_p97_5")], file.path(table_dir, "msa_productivity_losses_montecarlo_premature_30_69_nhis2024.csv"))
write_csv(detail, file.path(table_dir, "msa_productivity_losses_by_age_sex_premature_30_69_nhis2024.csv"))
write_text(file.path(table_dir, "msa_productivity_losses_report_premature_30_69.md"), paste(c(
  "# Premature 30-69 Productivity Losses Report",
  "",
  paste0("Generated: ", stamp()),
  "",
  paste0("Main productivity losses: ", fmt_money(totals$productivity_loss[totals$earnings_measure == "pernp_mean" & totals$productive_horizon == 65 & totals$discount_rate == 0.03][1]), ".")
), collapse = "\n"))
message("Computed productivity losses.")
