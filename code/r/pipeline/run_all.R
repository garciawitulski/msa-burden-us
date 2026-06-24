## Main R/Stata workflow driver for non-Stata R steps.
## Run Stata Cox scripts where indicated in README before R burden steps.

scripts <- c(
  "00_setup_project.R",
  "01_data_inventory.R",
  "02_download_or_prepare_ipums_extract.R",
  "03_build_msa_survival_dataset.R",
  "04_quality_checks.R",
  "07_download_nhis_2024_prevalence.R",
  "08_build_nhis_2024_msa_prevalence.R",
  "19_make_reviewer_revision_summaries.R",
  "06_burden_paf_deaths_yll.R",
  "09_download_or_prepare_external_mortality_lifetable.R",
  "10_compute_attributable_deaths_yll.R",
  "11_validate_burden_outputs.R",
  "16_compute_attributable_deaths_yll_premature_30_69.R",
  "13_compute_life_expectancy_gain.R",
  "14_compute_productivity_losses.R",
  "17_validate_premature_30_69_outputs.R",
  "12_make_manuscript_tables.R",
  "20_make_supplement_appendix_tables.R",
  "derive_subtotals.R"
)

for (script in scripts) {
  message("--- Running ", script)
  source(file.path("code", "r", "pipeline", script), local = new.env(parent = globalenv()))
}
message("R pipeline complete.")
