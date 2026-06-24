source(file.path("code", "r", "lib", "msaburden.R"))

ensure_standard_dirs()
full <- read_csv_required(here("data", "processed", "msa_survival_full.csv"))
missing_rows <- data.frame(
  variable = names(full),
  n_missing = vapply(full, function(x) sum(is.na(x) | x == ""), integer(1)),
  n_total = nrow(full),
  stringsAsFactors = FALSE
)
missing_rows$pct_missing <- missing_rows$n_missing / missing_rows$n_total
write_csv(missing_rows, here("outputs", "tables", "msa_missingness.csv"))

years <- sort(unique(num(full$year)))
year_rows <- do.call(rbind, lapply(years[!is.na(years)], function(y) {
  sub <- full[num(full$year) == y, ]
  data.frame(
    year = y,
    n_rows = nrow(sub),
    n_sample_adult_18plus = sum(sub$sample_adult == 1 & sub$adult_18plus == 1, na.rm = TRUE),
    n_main_complete_case = sum(sub$complete_case_main == 1, na.rm = TRUE)
  )
}))
write_csv(year_rows, here("outputs", "tables", "msa_year_inclusion.csv"))

desc <- data.frame(
  metric = c("rows", "mean_age", "weighted_insufficient_msa"),
  value = c(nrow(full), mean(num(full$age), na.rm = TRUE), weighted_mean(num(full$insufficient_msa), num(full$weight_sample_adult)))
)
write_csv(desc, here("data", "processed", "msa_descriptive_summary.csv"))
write_text(here("outputs", "logs", "quality_checks_log.txt"), paste(c(
  paste0("Generated: ", stamp()),
  paste0("Rows checked: ", nrow(full)),
  "Created missingness, year inclusion, and descriptive summaries."
), collapse = "\n"))
message("Quality checks complete.")
