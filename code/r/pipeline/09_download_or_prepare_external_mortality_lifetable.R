source(file.path("code", "r", "lib", "msaburden.R"))

ensure_standard_dirs()
ext <- here("data", "external")
docs <- here("docs")

death_required <- c("year", "sex", "age_group", "deaths_allcause", "population", "source", "notes")
life_single_required <- c("year", "sex", "age", "remaining_life_expectancy", "source", "notes")
life_group_required <- c("year", "sex", "age_group", "remaining_life_expectancy", "source", "notes")

has_cols <- function(path, cols) {
  file.exists(path) && all(cols %in% names(read.csv(path, nrows = 1, check.names = FALSE)))
}

mortality_file <- file.path(ext, "us_allcause_deaths_by_age_sex.csv")
life_single <- file.path(ext, "us_life_table_by_age_sex.csv")
life_group <- file.path(ext, "us_life_table_by_agegroup_sex.csv")

if (!has_cols(mortality_file, death_required)) {
  write_text(file.path(docs, "external_mortality_manual_download_instructions.md"), paste(c(
    "# Manual CDC WONDER Mortality Download Instructions",
    "",
    "Automatic mortality extraction is not part of the R-only public workflow.",
    "Do not fabricate death counts.",
    "",
    "Use CDC WONDER: Underlying Cause of Death, 2018-2024, Single Race.",
    "Create `data/external/us_allcause_deaths_by_age_sex.csv` with columns:",
    paste0("- `", death_required, "`")
  ), collapse = "\n"))
  append_issue_once("External mortality input missing", "Create `data/external/us_allcause_deaths_by_age_sex.csv` from CDC WONDER before running attributable deaths/YLL.")
}

if (!has_cols(life_single, life_single_required) || !has_cols(life_group, life_group_required)) {
  write_text(file.path(docs, "external_lifetable_manual_download_instructions.md"), paste(c(
    "# Manual NCHS Life Table Instructions",
    "",
    "Download NCHS United States Life Tables, 2023, NVSR Volume 74 Number 6.",
    "",
    "Male workbook: https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/NVSR/74-06/Table02.xlsx",
    "Female workbook: https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/NVSR/74-06/Table03.xlsx",
    "",
    "Create:",
    "- `data/external/us_life_table_by_age_sex.csv`",
    "- `data/external/us_life_table_by_agegroup_sex.csv`",
    "",
    "Required grouped columns:",
    paste0("- `", life_group_required, "`")
  ), collapse = "\n"))
  append_issue_once("External life-table input missing", "Create NCHS life-table CSV inputs before running YLL and life-expectancy modules.")
}

write_text(here("outputs", "logs", "09_external_mortality_lifetable.log"), paste(c(
  paste0("Generated: ", stamp()),
  paste0("Mortality input present: ", has_cols(mortality_file, death_required)),
  paste0("Life table single-age input present: ", has_cols(life_single, life_single_required)),
  paste0("Life table age-group input present: ", has_cols(life_group, life_group_required))
), collapse = "\n"))
message("External mortality/life-table check complete.")
