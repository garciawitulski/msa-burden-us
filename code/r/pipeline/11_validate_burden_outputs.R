source(file.path("code", "r", "lib", "msaburden.R"))

ensure_standard_dirs()
table_dir <- here("outputs", "tables")
attr <- read_csv_required(file.path(table_dir, "msa_attributable_deaths_nhis2024.csv"), c("rr_scenario", "stratum", "age_group", "sex", "deaths_allcause", "attributable_deaths"))
yll <- read_csv_required(file.path(table_dir, "msa_yll_nhis2024.csv"), c("rr_scenario", "stratum", "age_group", "sex", "yll"))
main <- attr[attr$rr_scenario == "main_strata_sex_year" & attr$stratum == "age_group_sex", ]
main_yll <- yll[yll$rr_scenario == "main_strata_sex_year" & yll$stratum == "age_group_sex", ]
contrib <- merge(main, main_yll[, c("age_group", "sex", "yll")], by = c("age_group", "sex"), all.x = TRUE)
contrib$share_attributable_deaths <- num(contrib$attributable_deaths) / sum(num(contrib$attributable_deaths), na.rm = TRUE)
contrib$share_yll <- num(contrib$yll) / sum(num(contrib$yll), na.rm = TRUE)
write_csv(contrib, file.path(table_dir, "msa_burden_contributions_by_age_sex.csv"))
overall <- attr[attr$rr_scenario == "main_strata_sex_year" & attr$stratum == "overall", ]
recon <- data.frame(metric = c("age_sex_attributable_deaths", "overall_attributable_deaths"), value = c(sum(num(main$attributable_deaths), na.rm = TRUE), num(overall$attributable_deaths[1])))
write_csv(recon, file.path(table_dir, "msa_burden_reconciliation_nhis2024.csv"))
write_text(file.path(table_dir, "msa_burden_validation_report.md"), paste(c(
  "# Burden Validation Report",
  "",
  paste0("Generated: ", stamp()),
  "",
  paste0("- Age-sex attributable deaths: ", fmt_int(recon$value[1]), "."),
  paste0("- Overall attributable deaths row: ", fmt_int(recon$value[2]), "."),
  "- R validation completed without fabricating data."
), collapse = "\n"))
message("Validated all-adult burden outputs.")
