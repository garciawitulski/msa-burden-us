source(file.path("code", "r", "lib", "msaburden.R"))

ensure_standard_dirs()
table_dir <- here("outputs", "tables")
out_dir <- here("outputs", "tables", "manuscript")
ensure_dir(out_dir)

optional_read <- function(path) if (file.exists(path)) read.csv(path, stringsAsFactors = FALSE, check.names = FALSE) else data.frame()

cox <- optional_read(file.path(table_dir, "reviewer_cox_sensitivity.csv"))
if (nrow(cox)) {
  tab2 <- data.frame(
    scenario = cox$scenario,
    model = cox$model_label,
    HR_95_CI = paste0(fmt_float(cox$hazard_ratio, 3), " (", fmt_float(cox$ci_lower, 3), "-", fmt_float(cox$ci_upper, 3), ")"),
    status = cox$status,
    stringsAsFactors = FALSE
  )
  save_table(tab2, file.path(out_dir, "table2_refined_cox_hazard_ratios.csv"), file.path(out_dir, "table2_refined_cox_hazard_ratios.md"), "Table 2. Cox Hazard Ratios")
}

prev <- optional_read(file.path(table_dir, "nhis_2024_msa_prevalence_premature_30_69_by_age_sex.csv"))
paf <- optional_read(file.path(table_dir, "msa_paf_insufficient_premature_30_69_nhis2024.csv"))
if (nrow(prev) && nrow(paf)) {
  paf_main <- paf[paf$rr_scenario == "main_hr_target_30_69" & paf$stratum == "age_group_sex", ]
  t3 <- merge(prev, paf_main[, c("age_group", "sex", "paf")], by = c("age_group", "sex"), all.x = TRUE)
  tab3 <- data.frame(
    age_group = t3$age_group,
    sex = t3$sex,
    n_unweighted = t3$n_unweighted,
    meeting_MSA_guideline_percent = 100 * num(t3$prevalence_meets_msa_guideline),
    insufficient_MSA_percent = 100 * num(t3$prevalence_insufficient_msa),
    PAF_percent = 100 * num(t3$paf),
    stringsAsFactors = FALSE
  )
  save_table(tab3, file.path(out_dir, "table3_nhis2024_prevalence_paf.csv"), file.path(out_dir, "table3_nhis2024_prevalence_paf.md"), "Table 3. NHIS 2024 Prevalence and PAF")
}

attr <- optional_read(file.path(table_dir, "msa_attributable_deaths_premature_30_69_nhis2024.csv"))
yll <- optional_read(file.path(table_dir, "msa_yll_premature_30_69_nhis2024.csv"))
if (nrow(attr) && nrow(yll)) {
  a <- attr[attr$rr_scenario == "main_hr_target_30_69" & attr$stratum == "age_group_sex", ]
  y <- yll[yll$rr_scenario == "main_hr_target_30_69" & yll$stratum == "age_group_sex", ]
  t4 <- merge(a, y[, c("age_group", "sex", "yll", "yll_p2_5", "yll_p97_5", "remaining_life_expectancy")], by = c("age_group", "sex"), all.x = TRUE)
  t4$PAF_percent <- NA_real_
  tab4 <- data.frame(
    age_group = t4$age_group,
    sex = t4$sex,
    all_cause_deaths = fmt_int(t4$deaths_allcause),
    attributable_deaths_95_UI = paste0(fmt_int(t4$attributable_deaths), " (", fmt_int(t4$attributable_deaths_p2_5), "-", fmt_int(t4$attributable_deaths_p97_5), ")"),
    YLL_95_UI = paste0(fmt_int(t4$yll), " (", fmt_int(t4$yll_p2_5), "-", fmt_int(t4$yll_p97_5), ")"),
    remaining_life_expectancy = fmt_float(t4$remaining_life_expectancy, 1),
    stringsAsFactors = FALSE
  )
  save_table(tab4, file.path(out_dir, "table4_attributable_deaths_yll.csv"), file.path(out_dir, "table4_attributable_deaths_yll.md"), "Table 4. Attributable Deaths and YLL")
}

prod <- optional_read(file.path(table_dir, "msa_productivity_losses_premature_30_69_nhis2024.csv"))
if (nrow(prod)) {
  save_table(prod, file.path(out_dir, "table5_productivity_losses.csv"), file.path(out_dir, "table5_productivity_losses.md"), "Table 5. Productivity Losses")
}

write_text(file.path(out_dir, "manuscript_results_summary.md"), paste(c(
  "# Manuscript Results Summary",
  "",
  paste0("Generated: ", stamp()),
  "",
  "Manuscript-ready tables were formatted from validated R/Stata outputs. Figures are rendered by `Rscript code/r/figures/render_all.R`."
), collapse = "\n"))
message("Created manuscript tables.")
