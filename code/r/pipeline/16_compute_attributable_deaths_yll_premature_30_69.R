source(file.path("code", "r", "lib", "msaburden.R"))

ensure_standard_dirs()
table_dir <- here("outputs", "tables")
ext <- here("data", "external")
paf <- read_csv_required(file.path(table_dir, "msa_paf_insufficient_premature_30_69_nhis2024.csv"), c("target_period", "stratum", "age_group", "sex", "prevalence_insufficient_msa", "rr_scenario", "hazard_ratio", "ci_lower", "ci_upper", "paf"))
deaths <- read_csv_required(file.path(ext, "us_allcause_deaths_by_age_sex_premature_30_69.csv"), c("year", "sex", "age_group", "deaths_allcause", "population"))
life <- read_csv_required(file.path(ext, "us_life_table_by_age_sex.csv"), c("year", "sex", "age", "remaining_life_expectancy"))
names(deaths)[names(deaths) == "year"] <- "mortality_year"
names(life)[names(life) == "year"] <- "life_table_year"
rep_age <- data.frame(age_group = c("30-34", "35-44", "45-54", "55-64", "65-69"), age = c(32, 40, 50, 60, 67))
life <- merge(rep_age, life, by = "age")
paf <- paf[paf$target_period == "premature_30_69" & paf$stratum == "age_group_sex", ]
merged <- merge(paf, deaths, by = c("age_group", "sex"), all.x = TRUE)
merged <- merge(merged, life[, c("age_group", "sex", "life_table_year", "remaining_life_expectancy")], by = c("age_group", "sex"), all.x = TRUE)
if (any(is.na(merged$deaths_allcause)) || any(is.na(merged$remaining_life_expectancy))) stop_issue("Missing matched premature burden strata", "Premature PAFs could not be matched to mortality or life-table inputs.")

compute <- function(rows, scenario) {
  rows <- rows[rows$rr_scenario == scenario, ]
  hr <- num(rows$hazard_ratio[1])
  lo <- num(rows$ci_lower[1])
  hi <- num(rows$ci_upper[1])
  set.seed(20260429 + sum(utf8ToInt(scenario)))
  draws <- exp(rnorm(10000, log(hr), (log(hi) - log(lo)) / (2 * 1.96)))
  paf_draws <- outer(draws - 1, num(rows$prevalence_insufficient_msa), function(h, p) p * h / (1 + p * h))
  death_draws <- sweep(paf_draws, 2, num(rows$deaths_allcause), "*")
  yll_draws <- sweep(death_draws, 2, num(rows$remaining_life_expectancy), "*")
  rows$attributable_deaths <- num(rows$paf) * num(rows$deaths_allcause)
  rows$yll <- rows$attributable_deaths * num(rows$remaining_life_expectancy)
  specs <- list(list(stratum = "overall", idx = seq_len(nrow(rows)), age = "all", sex = "all"))
  for (s in unique(rows$sex)) specs[[length(specs) + 1]] <- list(stratum = "sex", idx = which(rows$sex == s), age = "all", sex = s)
  for (a in unique(rows$age_group)) specs[[length(specs) + 1]] <- list(stratum = "age_group", idx = which(rows$age_group == a), age = a, sex = "all")
  for (i in seq_len(nrow(rows))) specs[[length(specs) + 1]] <- list(stratum = "age_group_sex", idx = i, age = rows$age_group[i], sex = rows$sex[i])
  deaths_out <- yll_out <- summary_out <- list()
  for (i in seq_along(specs)) {
    sp <- specs[[i]]
    idx <- sp$idx
    dq <- draw_summary(rowSums(death_draws[, idx, drop = FALSE]))
    yq <- draw_summary(rowSums(yll_draws[, idx, drop = FALSE]))
    common <- data.frame(rr_scenario = scenario, target_period = "premature_30_69", stratum = sp$stratum, age_group = sp$age, sex = sp$sex, mortality_year = max(num(rows$mortality_year), na.rm = TRUE), life_table_year = max(num(rows$life_table_year), na.rm = TRUE), deaths_allcause = sum(num(rows$deaths_allcause[idx])), population = sum(num(rows$population[idx]), na.rm = TRUE), n_draws = 10000)
    deaths_out[[i]] <- cbind(common, attributable_deaths = sum(rows$attributable_deaths[idx]), attributable_deaths_median = dq["median"], attributable_deaths_p2_5 = dq["p2_5"], attributable_deaths_p97_5 = dq["p97_5"])
    yll_out[[i]] <- cbind(common, remaining_life_expectancy = ifelse(sp$stratum == "age_group_sex", rows$remaining_life_expectancy[idx], NA), yll = sum(rows$yll[idx]), yll_median = yq["median"], yll_p2_5 = yq["p2_5"], yll_p97_5 = yq["p97_5"])
    if (sp$stratum == "overall") summary_out[[1]] <- cbind(common, hazard_ratio = hr, ci_lower = lo, ci_upper = hi, attributable_deaths = sum(rows$attributable_deaths[idx]), attributable_deaths_p2_5 = dq["p2_5"], attributable_deaths_p97_5 = dq["p97_5"], yll = sum(rows$yll[idx]), yll_p2_5 = yq["p2_5"], yll_p97_5 = yq["p97_5"])
  }
  list(deaths = do.call(rbind, deaths_out), yll = do.call(rbind, yll_out), summary = do.call(rbind, summary_out))
}
results <- lapply(sort(unique(merged$rr_scenario)), function(s) compute(merged, s))
write_csv(do.call(rbind, lapply(results, `[[`, "deaths")), file.path(table_dir, "msa_attributable_deaths_premature_30_69_nhis2024.csv"))
write_csv(do.call(rbind, lapply(results, `[[`, "yll")), file.path(table_dir, "msa_yll_premature_30_69_nhis2024.csv"))
write_csv(do.call(rbind, lapply(results, `[[`, "summary")), file.path(table_dir, "msa_burden_summary_premature_30_69_nhis2024.csv"))
message("Computed premature 30-69 attributable deaths and YLL.")
