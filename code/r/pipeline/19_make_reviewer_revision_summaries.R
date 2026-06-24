source(file.path("code", "r", "lib", "msaburden.R"))

ensure_standard_dirs()
table_dir <- here("outputs", "tables")
full <- read_csv_required(here("data", "processed", "msa_survival_full.csv"))
covars <- c("msa_days_week", "aerobic_minutes_meq_weekly", "age", "sex", "race_ethnicity", "education", "poverty", "bmi", "smoking_status", "alcohol_use", "self_rated_health", "diabetes", "hypertension", "cvd_history", "cancer_history")
rows <- lapply(covars[covars %in% names(full)], function(v) {
  data.frame(variable = v, n_missing = sum(is.na(full[[v]]) | full[[v]] == ""), pct_missing = 100 * mean(is.na(full[[v]]) | full[[v]] == ""))
})
miss <- do.call(rbind, rows)
write_csv(miss, file.path(table_dir, "reviewer_missingness_impact.csv"))
write_text(file.path(table_dir, "reviewer_missingness_impact.md"), markdown_table(miss, "Reviewer Missingness Impact"))

cox_path <- file.path(table_dir, "reviewer_cox_sensitivity.csv")
if (file.exists(cox_path)) {
  cox <- read.csv(cox_path, stringsAsFactors = FALSE, check.names = FALSE)
  write_text(file.path(table_dir, "reviewer_cox_sensitivity.md"), markdown_table(cox, "Reviewer Cox Sensitivity"))
}
message("Created reviewer revision summaries.")
