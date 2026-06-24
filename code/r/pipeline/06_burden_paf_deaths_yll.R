source(file.path("code", "r", "lib", "msaburden.R"))

ensure_standard_dirs()
table_dir <- here("outputs", "tables")

weighted_summary <- function(df, stratum, year = "all", age_group = "all", sex = "all") {
  w <- num(df$weight_sample_adult)
  e <- num(df$insufficient_msa)
  ok <- is.finite(w) & w > 0 & !is.na(e)
  data.frame(
    stratum = stratum, year = year, age_group = age_group, sex = sex,
    n_unweighted = sum(ok), n_exposed = sum(e[ok] == 1, na.rm = TRUE),
    weighted_total = sum(w[ok]), weighted_exposed = sum(w[ok] * e[ok]),
    prevalence_insufficient_msa = sum(w[ok] * e[ok]) / sum(w[ok]),
    stringsAsFactors = FALSE
  )
}

build_prev <- function(df) {
  rows <- list(weighted_summary(df, "overall"))
  for (a in sort(unique(na.omit(df$age_group)))) rows[[length(rows) + 1]] <- weighted_summary(df[df$age_group == a, ], "age_group", age_group = a)
  for (s in sort(unique(na.omit(df$sex)))) rows[[length(rows) + 1]] <- weighted_summary(df[df$sex == s, ], "sex", sex = s)
  for (a in sort(unique(na.omit(df$age_group)))) for (s in sort(unique(na.omit(df$sex)))) {
    sub <- df[df$age_group == a & df$sex == s, ]
    if (nrow(sub)) rows[[length(rows) + 1]] <- weighted_summary(sub, "age_group_sex", age_group = a, sex = s)
  }
  do.call(rbind, rows)
}

choose_hr <- function(rows, dataset, scenario) {
  sub <- rows[rows$dataset == dataset & rows$exposure_spec == "Guideline" & rows$term == "1.insufficient_msa", ]
  if (!nrow(sub)) stop_issue("Unable to identify refined HR", paste0("No refined HR found for dataset `", dataset, "`."))
  row <- sub[1, ]
  data.frame(
    rr_scenario = scenario, dataset = dataset, model_label = row$model_label,
    exposure_spec = row$exposure_spec, term = row$term,
    hazard_ratio = num(row$hazard_ratio), ci_lower = num(row$ci_lower),
    ci_upper = num(row$ci_upper), p_value = if ("p_value" %in% names(row)) num(row$p_value) else NA_real_,
    stringsAsFactors = FALSE
  )
}

build_paf <- function(prev, hrs) {
  do.call(rbind, lapply(seq_len(nrow(hrs)), function(i) {
    hr <- hrs[i, ]
    out <- prev
    out$rr_scenario <- hr$rr_scenario
    out$hr_dataset <- hr$dataset
    out$hr_model_label <- hr$model_label
    out$hazard_ratio <- hr$hazard_ratio
    out$ci_lower <- hr$ci_lower
    out$ci_upper <- hr$ci_upper
    out$paf <- paf_value(out$prevalence_insufficient_msa, hr$hazard_ratio)
    out
  }))
}

build_paf_mc <- function(prev, hrs, n_draws = 10000L) {
  rows <- list()
  k <- 1
  for (i in seq_len(nrow(hrs))) {
    hr <- hrs[i, ]
    for (j in seq_len(nrow(prev))) {
      draws <- simulate_paf(prev$prevalence_insufficient_msa[j], hr$hazard_ratio, hr$ci_lower, hr$ci_upper, n_draws)
      q <- draw_summary(draws)
      rows[[k]] <- cbind(prev[j, ], rr_scenario = hr$rr_scenario, hazard_ratio = hr$hazard_ratio, ci_lower = hr$ci_lower, ci_upper = hr$ci_upper, n_draws = n_draws, paf_median = q["median"], paf_p2_5 = q["p2_5"], paf_p97_5 = q["p97_5"])
      k <- k + 1
    }
  }
  do.call(rbind, rows)
}

full <- read_csv_required(here("data", "processed", "msa_survival_full.csv"), c("year", "sample_adult", "adult_18plus", "insufficient_msa", "weight_sample_adult", "sex"))
if (!"age_group" %in% names(full)) full$age_group <- if ("age_cat" %in% names(full)) full$age_cat else age_group_18plus(full$age)
prev_df <- full[full$sample_adult == 1 & full$adult_18plus == 1 & !is.na(full$insufficient_msa) & num(full$weight_sample_adult) > 0, ]
prev <- build_prev(prev_df)
write_csv(prev, file.path(table_dir, "msa_prevalence_insufficient.csv"))

refined <- read_csv_required(file.path(table_dir, "refined_cox_msa_allcause.csv"), c("dataset", "model_label", "exposure_spec", "term", "hazard_ratio", "ci_lower", "ci_upper"))
hrs <- rbind(
  choose_hr(refined, "main", "main_strata_sex_year"),
  choose_hr(refined, "lag24", "lag24_strata_sex_year")
)
reviewer_path <- file.path(table_dir, "reviewer_cox_sensitivity.csv")
hr_inputs <- data.frame()
if (file.exists(reviewer_path)) {
  reviewer <- read_csv_required(reviewer_path)
  reviewer <- reviewer[reviewer$status == "completed", ]
  pick <- function(sources, scenario, note) {
    for (source in sources) {
      matched <- reviewer[reviewer$scenario == source, ]
      if (nrow(matched)) {
        row <- matched[1, ]
        return(data.frame(scenario = scenario, analysis_population = row$analysis_population, exposure = "insufficient_msa", hr = num(row$hazard_ratio), ci_lower = num(row$ci_lower), ci_upper = num(row$ci_upper), source_model = paste(row$scenario, row$model_label, row$design_type, row$term, sep = " / "), notes = note))
      }
    }
    NULL
  }
  hr_inputs <- do.call(rbind, Filter(Negate(is.null), list(
    pick(c("target_30_69_svy", "target_30_69_current"), "main_hr_target_30_69", "Reviewer-response primary HR."),
    pick(c("target_30_69_lag24"), "lag24_hr_target_30_69", "Reviewer-response lagged sensitivity HR.")
  )))
}
hr_inputs <- rbind(
  hr_inputs,
  data.frame(scenario = "main_hr_adult_refined", analysis_population = "adult_refined_survival_hr_applied_to_premature_30_69", exposure = "insufficient_msa", hr = hrs$hazard_ratio[1], ci_lower = hrs$ci_lower[1], ci_upper = hrs$ci_upper[1], source_model = paste(hrs$dataset[1], hrs$model_label[1], sep = " / "), notes = "Adult refined comparison sensitivity."),
  data.frame(scenario = "lag24_hr_adult_refined", analysis_population = "adult_refined_survival_hr_applied_to_premature_30_69", exposure = "insufficient_msa", hr = hrs$hazard_ratio[2], ci_lower = hrs$ci_lower[2], ci_upper = hrs$ci_upper[2], source_model = paste(hrs$dataset[2], hrs$model_label[2], sep = " / "), notes = "Adult lagged comparison sensitivity.")
)
write_csv(hr_inputs, file.path(table_dir, "hr_inputs_for_burden.csv"))

paf_rows <- build_paf(prev, hrs)
paf_mc <- build_paf_mc(prev, hrs)
write_csv(paf_rows, file.path(table_dir, "msa_paf_insufficient.csv"))
write_csv(paf_mc, file.path(table_dir, "msa_paf_insufficient_montecarlo.csv"))

nhis2024 <- here("data", "processed", "nhis_2024", "nhis_2024_msa_prevalence_dataset.csv")
if (file.exists(nhis2024)) {
  n24 <- read.csv(nhis2024, stringsAsFactors = FALSE, check.names = FALSE)
  n24$insufficient_msa <- n24$insufficient_msa_2024
  n24 <- n24[n24$sample_adult == 1 & n24$adult_18plus == 1 & !is.na(n24$insufficient_msa) & num(n24$weight_sample_adult) > 0, ]
  p24 <- build_prev(n24)
  p24 <- cbind(target_period = "nhis_2024_current", target_period_label = "NHIS 2024 current prevalence", period_role = "preferred current prevalence", main_present_day_prevalence = 1, period_start_year = 2024, period_end_year = 2024, years_included = "2024", p24)
  paf24 <- build_paf(p24, hrs)
  paf24mc <- build_paf_mc(p24, hrs)
  write_csv(paf24, file.path(table_dir, "msa_paf_insufficient_using_nhis2024.csv"))
  write_csv(paf24mc, file.path(table_dir, "msa_paf_insufficient_montecarlo_using_nhis2024.csv"))
}

prem_files <- c(
  overall = "nhis_2024_msa_prevalence_premature_30_69_overall.csv",
  sex = "nhis_2024_msa_prevalence_premature_30_69_by_sex.csv",
  age = "nhis_2024_msa_prevalence_premature_30_69_by_age.csv",
  age_sex = "nhis_2024_msa_prevalence_premature_30_69_by_age_sex.csv"
)
if (all(file.exists(file.path(table_dir, prem_files)))) {
  prem_rows <- list()
  add <- function(path, stratum, age = "all", sex = "all") {
    d <- read.csv(path, stringsAsFactors = FALSE, check.names = FALSE)
    if (!"age_group" %in% names(d)) d$age_group <- age
    if (!"sex" %in% names(d)) d$sex <- sex
    data.frame(target_period = "premature_30_69", target_period_label = "NHIS 2024 premature mortality age 30-69 prevalence", period_role = "preferred main premature mortality prevalence", main_present_day_prevalence = 1, period_start_year = 2024, period_end_year = 2024, years_included = "2024", analysis_population = "premature_30_69", stratum = stratum, year = "all", age_group = d$age_group, sex = d$sex, n_unweighted = d$n_unweighted, weighted_total = d$weighted_total, weighted_exposed = d$weighted_insufficient_msa, prevalence_meets_msa_guideline = d$prevalence_meets_msa_guideline, prevalence_insufficient_msa = d$prevalence_insufficient_msa)
  }
  prem_prev <- rbind(
    add(file.path(table_dir, prem_files["overall"]), "overall"),
    add(file.path(table_dir, prem_files["sex"]), "sex", age = "all"),
    add(file.path(table_dir, prem_files["age"]), "age_group", sex = "all"),
    add(file.path(table_dir, prem_files["age_sex"]), "age_group_sex")
  )
  prem_hrs <- data.frame(rr_scenario = hr_inputs$scenario, dataset = hr_inputs$analysis_population, model_label = hr_inputs$source_model, hazard_ratio = hr_inputs$hr, ci_lower = hr_inputs$ci_lower, ci_upper = hr_inputs$ci_upper)
  write_csv(build_paf(prem_prev, prem_hrs), file.path(table_dir, "msa_paf_insufficient_premature_30_69_nhis2024.csv"))
  write_csv(build_paf_mc(prem_prev, prem_hrs), file.path(table_dir, "msa_paf_insufficient_montecarlo_premature_30_69_nhis2024.csv"))
}

write_text(file.path(table_dir, "burden_readiness_report.md"), paste(c(
  "# Burden Readiness Report",
  "",
  paste0("Generated: ", stamp()),
  "",
  "- Prevalence and PAF files were generated in R.",
  "- External mortality, life-table, and productivity files are required for downstream burden outputs.",
  "- Estimates are modelled comparative-risk estimates, not direct causal proof."
), collapse = "\n"))
message("PAF pipeline complete.")
