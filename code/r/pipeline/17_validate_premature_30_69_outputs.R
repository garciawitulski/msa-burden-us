source(file.path("code", "r", "lib", "msaburden.R"))

ensure_standard_dirs()
table_dir <- here("outputs", "tables")
attr <- read_csv_required(file.path(table_dir, "msa_attributable_deaths_premature_30_69_nhis2024.csv"), c("rr_scenario", "stratum", "age_group", "sex", "deaths_allcause", "attributable_deaths"))
yll <- read_csv_required(file.path(table_dir, "msa_yll_premature_30_69_nhis2024.csv"), c("rr_scenario", "stratum", "age_group", "sex", "yll"))
expected <- c("30-34", "35-44", "45-54", "55-64", "65-69")
found <- sort(unique(attr$age_group[attr$stratum == "age_group"]))
if (!identical(sort(found), expected)) append_issue_once("Unexpected premature age groups", paste("Expected", paste(expected, collapse = ", "), "but found", paste(found, collapse = ", ")))
main <- attr[attr$rr_scenario == "main_hr_target_30_69" & attr$stratum == "age_group_sex", ]
main_yll <- yll[yll$rr_scenario == "main_hr_target_30_69" & yll$stratum == "age_group_sex", ]
contrib <- merge(main, main_yll[, c("age_group", "sex", "yll")], by = c("age_group", "sex"), all.x = TRUE)
contrib$share_attributable_deaths <- num(contrib$attributable_deaths) / sum(num(contrib$attributable_deaths), na.rm = TRUE)
contrib$share_yll <- num(contrib$yll) / sum(num(contrib$yll), na.rm = TRUE)
write_csv(contrib, file.path(table_dir, "msa_burden_contributions_by_age_sex_premature_30_69.csv"))
overall <- attr[attr$rr_scenario == "main_hr_target_30_69" & attr$stratum == "overall", ]
recon <- data.frame(metric = c("age_sex_attributable_deaths", "overall_attributable_deaths"), value = c(sum(num(main$attributable_deaths), na.rm = TRUE), num(overall$attributable_deaths[1])))
write_csv(recon, file.path(table_dir, "msa_burden_reconciliation_premature_30_69.csv"))
write_text(file.path(table_dir, "msa_burden_validation_report_premature_30_69.md"), paste(c(
  "# Premature 30-69 Burden Validation Report",
  "",
  paste0("Generated: ", stamp()),
  "",
  paste0("- Attributable premature deaths: ", fmt_int(sum(num(main$attributable_deaths), na.rm = TRUE)), "."),
  paste0("- Premature YLL: ", fmt_int(sum(num(contrib$yll), na.rm = TRUE)), "."),
  "- Expected premature age groups were checked."
), collapse = "\n"))
message("Validated premature 30-69 burden outputs.")
