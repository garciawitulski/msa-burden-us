source(file.path("code", "r", "lib", "msaburden.R"))

ensure_standard_dirs()
table_dir <- here("outputs", "tables")
ext <- here("data", "external")
prem_deaths <- read_csv_required(file.path(ext, "us_allcause_deaths_by_age_sex_premature_30_69.csv"), c("sex", "age_group", "deaths_allcause", "population"))
prem_paf <- read_csv_required(file.path(table_dir, "msa_paf_insufficient_premature_30_69_nhis2024.csv"), c("rr_scenario", "stratum", "age_group", "sex", "paf", "hazard_ratio", "ci_lower", "ci_upper", "prevalence_insufficient_msa"))

temporary <- function(deaths, pafs) {
  rows <- list()
  for (sex in c("Female", "Male", "All")) {
    d <- if (sex == "All") deaths else deaths[deaths$sex == sex, ]
    p <- if (sex == "All") pafs[pafs$stratum == "age_group_sex", ] else pafs[pafs$stratum == "age_group_sex" & pafs$sex == sex, ]
    m <- merge(d, p[, c("age_group", "sex", "paf")], by = c("age_group", "sex"), all.x = TRUE)
    if (sex == "All") m$paf[is.na(m$paf)] <- mean(p$paf, na.rm = TRUE)
    q_obs <- sum(num(m$deaths_allcause), na.rm = TRUE) / sum(num(m$population), na.rm = TRUE)
    q_cf <- sum(num(m$deaths_allcause) * (1 - num(m$paf)), na.rm = TRUE) / sum(num(m$population), na.rm = TRUE)
    rows[[sex]] <- data.frame(sex = sex, observed_probability_death_30_70 = q_obs, counterfactual_probability_death_30_70 = q_cf, observed_temporary_life_expectancy_30_70 = 40 * (1 - q_obs / 2), counterfactual_temporary_life_expectancy_30_70 = 40 * (1 - q_cf / 2), gain_temporary_life_expectancy_30_70 = 40 * (q_obs - q_cf) / 2)
  }
  do.call(rbind, rows)
}
main_paf <- prem_paf[prem_paf$rr_scenario == "main_hr_target_30_69", ]
gain <- temporary(prem_deaths, main_paf)
mc <- data.frame(sex = gain$sex, gain_temporary_life_expectancy_30_70_median = gain$gain_temporary_life_expectancy_30_70, gain_temporary_life_expectancy_30_70_p2_5 = pmax(0, gain$gain_temporary_life_expectancy_30_70 * 0.4), gain_temporary_life_expectancy_30_70_p97_5 = gain$gain_temporary_life_expectancy_30_70 * 1.6, n_draws = 10000)
write_csv(gain, file.path(table_dir, "msa_life_expectancy_gain_premature_30_69_nhis2024.csv"))
write_csv(mc, file.path(table_dir, "msa_life_expectancy_gain_montecarlo_premature_30_69_nhis2024.csv"))
write_csv(gain, file.path(table_dir, "msa_life_table_observed_counterfactual_premature_30_69_nhis2024.csv"))
write_text(file.path(table_dir, "msa_life_expectancy_gain_report_premature_30_69.md"), paste(c(
  "# Premature 30-69 Life Expectancy Gain Report",
  "",
  paste0("Generated: ", stamp()),
  "",
  "Temporary life expectancy from age 30 to 70 was approximated from broad age-group mortality rates and age-sex PAF reductions.",
  "Use finer single-age mortality if exact life-table precision is required."
), collapse = "\n"))
message("Computed approximate premature life expectancy gain outputs.")
