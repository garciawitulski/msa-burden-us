source(file.path("code", "r", "lib", "msaburden.R"))

ensure_standard_dirs()
table_dir <- here("outputs", "tables")
ext <- here("data", "external")

paf <- read_csv_required(file.path(table_dir, "msa_paf_insufficient_using_nhis2024.csv"), c("target_period", "stratum", "age_group", "sex", "prevalence_insufficient_msa", "rr_scenario", "hazard_ratio", "ci_lower", "ci_upper", "paf"))
deaths <- read_csv_required(file.path(ext, "us_allcause_deaths_by_age_sex.csv"), c("year", "sex", "age_group", "deaths_allcause", "population", "source", "notes"))
life <- read_csv_required(file.path(ext, "us_life_table_by_agegroup_sex.csv"), c("year", "sex", "age_group", "remaining_life_expectancy", "source", "notes"))
names(deaths)[names(deaths) == "year"] <- "mortality_year"
names(deaths)[names(deaths) == "source"] <- "mortality_source"
names(deaths)[names(deaths) == "notes"] <- "mortality_notes"
names(life)[names(life) == "year"] <- "life_table_year"
names(life)[names(life) == "source"] <- "life_table_source"
names(life)[names(life) == "notes"] <- "life_table_notes"
paf <- paf[paf$target_period == "nhis_2024_current" & paf$stratum == "age_group_sex", ]
merged <- merge(paf, deaths, by = c("age_group", "sex"), all.x = TRUE)
merged <- merge(merged, life, by = c("age_group", "sex"), all.x = TRUE)
if (any(is.na(merged$deaths_allcause)) || any(is.na(merged$remaining_life_expectancy))) {
  stop_issue("Missing matched burden strata", "Could not match all NHIS 2024 age-sex PAF strata to deaths and life-table inputs.")
}

group_rows <- function(rows, scenario) {
  rows <- rows[rows$rr_scenario == scenario, ]
  if (!nrow(rows)) return(NULL)
  hr <- num(rows$hazard_ratio[1])
  lo <- num(rows$ci_lower[1])
  hi <- num(rows$ci_upper[1])
  set.seed(20260429 + sum(utf8ToInt(scenario)))
  hr_draws <- exp(rnorm(10000, log(hr), (log(hi) - log(lo)) / (2 * 1.96)))
  p <- num(rows$prevalence_insufficient_msa)
  paf_draws <- outer(hr_draws - 1, p, function(h, pp) pp * h / (1 + pp * h))
  death_draws <- sweep(paf_draws, 2, num(rows$deaths_allcause), "*")
  yll_draws <- sweep(death_draws, 2, num(rows$remaining_life_expectancy), "*")
  rows$attributable_deaths <- num(rows$paf) * num(rows$deaths_allcause)
  rows$yll <- rows$attributable_deaths * num(rows$remaining_life_expectancy)
  specs <- list(
    overall = list(idx = seq_len(nrow(rows)), age = "all", sex = "all"),
    sex = NULL,
    age_group = NULL,
    age_group_sex = NULL
  )
  for (s in unique(rows$sex)) specs[[paste0("sex:", s)]] <- list(stratum = "sex", idx = which(rows$sex == s), age = "all", sex = s)
  for (a in unique(rows$age_group)) specs[[paste0("age:", a)]] <- list(stratum = "age_group", idx = which(rows$age_group == a), age = a, sex = "all")
  for (i in seq_len(nrow(rows))) specs[[paste0("cell:", i)]] <- list(stratum = "age_group_sex", idx = i, age = rows$age_group[i], sex = rows$sex[i])
  specs$overall$stratum <- "overall"
  deaths_out <- list()
  yll_out <- list()
  summary_out <- list()
  k <- 1
  for (sp in specs[!vapply(specs, is.null, logical(1))]) {
    idx <- sp$idx
    dsum <- rowSums(death_draws[, idx, drop = FALSE])
    ysum <- rowSums(yll_draws[, idx, drop = FALSE])
    dq <- draw_summary(dsum)
    yq <- draw_summary(ysum)
    common <- data.frame(rr_scenario = scenario, target_period = "nhis_2024_current", stratum = sp$stratum, age_group = sp$age, sex = sp$sex, mortality_year = max(num(rows$mortality_year), na.rm = TRUE), life_table_year = max(num(rows$life_table_year), na.rm = TRUE), deaths_allcause = sum(num(rows$deaths_allcause[idx])), population = sum(num(rows$population[idx])), n_draws = 10000)
    deaths_out[[k]] <- cbind(common, attributable_deaths = sum(rows$attributable_deaths[idx]), attributable_deaths_median = dq["median"], attributable_deaths_p2_5 = dq["p2_5"], attributable_deaths_p97_5 = dq["p97_5"], mortality_source = rows$mortality_source[1])
    yll_out[[k]] <- cbind(common, remaining_life_expectancy = ifelse(sp$stratum == "age_group_sex", rows$remaining_life_expectancy[idx], NA), yll = sum(rows$yll[idx]), yll_median = yq["median"], yll_p2_5 = yq["p2_5"], yll_p97_5 = yq["p97_5"], life_table_source = rows$life_table_source[1])
    if (sp$stratum == "overall") summary_out[[1]] <- cbind(common, hazard_ratio = hr, ci_lower = lo, ci_upper = hi, attributable_deaths = sum(rows$attributable_deaths[idx]), attributable_deaths_median = dq["median"], attributable_deaths_p2_5 = dq["p2_5"], attributable_deaths_p97_5 = dq["p97_5"], yll = sum(rows$yll[idx]), yll_median = yq["median"], yll_p2_5 = yq["p2_5"], yll_p97_5 = yq["p97_5"])
    k <- k + 1
  }
  list(deaths = do.call(rbind, deaths_out), yll = do.call(rbind, yll_out), summary = do.call(rbind, summary_out))
}

results <- lapply(sort(unique(merged$rr_scenario)), function(s) group_rows(merged, s))
write_csv(do.call(rbind, lapply(results, `[[`, "deaths")), file.path(table_dir, "msa_attributable_deaths_nhis2024.csv"))
write_csv(do.call(rbind, lapply(results, `[[`, "yll")), file.path(table_dir, "msa_yll_nhis2024.csv"))
write_csv(do.call(rbind, lapply(results, `[[`, "summary")), file.path(table_dir, "msa_burden_summary_nhis2024.csv"))
message("Computed attributable deaths and YLL.")
