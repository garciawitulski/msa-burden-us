source(file.path("code", "r", "lib", "msaburden.R"))

ensure_standard_dirs()
raw_dir <- here("data", "raw")
processed_dir <- here("data", "processed")

find_raw <- function() {
  candidates <- c(
    list.files(raw_dir, pattern = "\\.csv(\\.gz)?$", full.names = TRUE),
    list.files(raw_dir, pattern = "\\.dta$", full.names = TRUE)
  )
  candidates <- candidates[file.exists(candidates)]
  if (!length(candidates)) stop_issue("Missing raw NHIS-LMF input", "No supported raw IPUMS data file was found in `data/raw/`.")
  candidates[[1]]
}

read_raw <- function(path) {
  if (grepl("\\.dta$", path, ignore.case = TRUE)) {
    if (requireNamespace("haven", quietly = TRUE)) return(as.data.frame(haven::read_dta(path)))
    if (requireNamespace("foreign", quietly = TRUE)) return(as.data.frame(foreign::read.dta(path, convert.factors = FALSE)))
    stop_issue("Cannot read Stata raw file", "Install R package `haven` or `foreign`, or place a CSV extract in `data/raw/`.")
  }
  read.csv(path, stringsAsFactors = FALSE, check.names = FALSE)
}

recode_weekly <- function(x) {
  x <- num(x)
  out <- rep(NA_real_, length(x))
  out[x >= 1 & x <= 92] <- x[x >= 1 & x <= 92]
  out[x == 94] <- 0.5
  out[x == 95] <- 0
  out
}

recode_minutes <- function(x, freq) {
  x <- num(x)
  out <- rep(NA_real_, length(x))
  out[x >= 1 & x <= 995] <- x[x >= 1 & x <= 995]
  out[!is.na(freq) & freq == 0] <- 0
  out
}

binary_codes <- function(x, yes = 2, no = 1) {
  x <- num(x)
  out <- rep(NA_real_, length(x))
  out[x %in% no] <- 0
  out[x %in% yes] <- 1
  out
}

race_ethnicity <- function(df) {
  race <- if ("RACEA" %in% names(df)) num(df$RACEA) else rep(NA_real_, nrow(df))
  hisp <- if ("HISPETH" %in% names(df)) num(df$HISPETH) else rep(NA_real_, nrow(df))
  out <- rep(NA_character_, nrow(df))
  out[hisp >= 20 & hisp <= 70] <- "Hispanic"
  non <- hisp == 10
  out[non & race == 100] <- "Non-Hispanic White"
  out[non & race == 200] <- "Non-Hispanic Black"
  out[non & race >= 300 & race <= 399] <- "Non-Hispanic American Indian/Alaska Native"
  out[non & race >= 400 & race <= 499] <- "Non-Hispanic Asian/Pacific Islander"
  out[non & race >= 500 & race <= 599] <- "Non-Hispanic Other race"
  out[non & race >= 600 & race <= 699] <- "Non-Hispanic Multiple race"
  out
}

educ_cat <- function(x) {
  x <- num(x)
  out <- rep(NA_character_, length(x))
  out[x >= 100 & x <= 199] <- "Less than high school"
  out[x >= 200 & x <= 299] <- "High school/GED"
  out[x >= 300 & x <= 399] <- "Some college/AA"
  out[x >= 400 & x <= 499] <- "Bachelor's degree"
  out[x >= 500 & x <= 599] <- "Graduate/professional degree"
  out
}

poverty_cat <- function(x) {
  x <- num(x)
  out <- rep(NA_character_, length(x))
  out[x >= 10 & x <= 14] <- "<1.00 poverty ratio"
  out[x >= 20 & x <= 25] <- "1.00-1.99 poverty ratio"
  out[x >= 30 & x <= 38] <- ">=2.00 poverty ratio"
  out
}

followup_months <- function(df, died) {
  for (candidate in c("PERMTH_INT", "PERMTH_EXM", "PERMTH", "FOLLOWUP_MONTHS")) {
    if (candidate %in% names(df)) return(list(value = num(df[[candidate]]), source = candidate, note = "Exact follow-up-month variable from extract."))
  }
  required <- c("YEAR", "QUARTER", "MORTDODY", "MORTDODQ")
  require_columns(df, required, "raw NHIS extract")
  start_q <- num(df$YEAR) * 4 + num(df$QUARTER)
  end_q <- rep(2019 * 4 + 4, nrow(df))
  death_year <- num(df$MORTDODY)
  death_q <- num(df$MORTDODQ)
  valid_death <- died == 1 & death_year >= 1900 & death_year <= 2019 & death_q >= 1 & death_q <= 4
  end_q[valid_death] <- death_year[valid_death] * 4 + death_q[valid_death]
  fu <- (end_q - start_q) * 3
  fu[valid_death & !is.na(fu) & fu <= 0] <- 1.5
  fu[died == 1 & !valid_death] <- NA_real_
  fu[!(num(df$QUARTER) >= 1 & num(df$QUARTER) <= 4)] <- NA_real_
  append_issue_once("Approximate follow-up time used", "No exact person-month follow-up variable was present. Follow-up was approximated from survey year/quarter to death year/quarter or December 31, 2019.")
  list(value = fu, source = "YEAR+QUARTER+MORTDODY+MORTDODQ", note = "Quarter-based approximate follow-up.")
}

path <- find_raw()
df <- read_raw(path)
names(df) <- toupper(names(df))
required <- c("YEAR", "QUARTER", "NHISPID", "ASTATFLG", "AGE", "MORTELIG", "MORTSTAT", "MORTDODY", "MORTDODQ", "MORTWTSA", "STRONGFWK")
require_columns(df, required, rel_path(path))

age <- num(df$AGE)
msa_days <- recode_weekly(df$STRONGFWK)
msa_cat <- rep(NA_real_, length(msa_days))
msa_cat[!is.na(msa_days) & msa_days < 1] <- 0
msa_cat[msa_days == 1] <- 1
msa_cat[msa_days == 2] <- 2
msa_cat[msa_days >= 3 & msa_days <= 4] <- 3
msa_cat[msa_days >= 5] <- 4
mod_freq <- if ("MOD10FWK" %in% names(df)) recode_weekly(df$MOD10FWK) else rep(NA_real_, nrow(df))
vig_freq <- if ("VIG10FWK" %in% names(df)) recode_weekly(df$VIG10FWK) else rep(NA_real_, nrow(df))
mod_min <- if ("MOD10DMIN" %in% names(df)) recode_minutes(df$MOD10DMIN, mod_freq) else rep(NA_real_, nrow(df))
vig_min <- if ("VIG10DMIN" %in% names(df)) recode_minutes(df$VIG10DMIN, vig_freq) else rep(NA_real_, nrow(df))
aerobic <- mod_freq * mod_min + 2 * vig_freq * vig_min
aerobic_category <- rep(NA_character_, length(aerobic))
aerobic_category[!is.na(aerobic) & aerobic == 0] <- "inactive"
aerobic_category[!is.na(aerobic) & aerobic > 0 & aerobic < 150] <- "insufficiently active"
aerobic_category[!is.na(aerobic) & aerobic >= 150] <- "meets guideline"
died <- ifelse(num(df$MORTSTAT) == 1, 1, ifelse(num(df$MORTSTAT) == 2, 0, NA_real_))
fu <- followup_months(df, died)
cvd_history <- pmax(
  if ("CHEARTDIEV" %in% names(df)) binary_codes(df$CHEARTDIEV) else NA_real_,
  if ("HEARTATTEV" %in% names(df)) binary_codes(df$HEARTATTEV) else NA_real_,
  if ("STROKEV" %in% names(df)) binary_codes(df$STROKEV) else NA_real_,
  na.rm = TRUE
)
cvd_history[!is.finite(cvd_history)] <- NA_real_

bmi <- if ("BMICALC" %in% names(df)) ifelse(num(df$BMICALC) >= 1 & num(df$BMICALC) <= 995, num(df$BMICALC), NA) else NA_real_
bmi_cat <- rep(NA_character_, length(bmi))
bmi_cat[!is.na(bmi) & bmi < 18.5] <- "underweight"
bmi_cat[!is.na(bmi) & bmi >= 18.5 & bmi < 25] <- "normal weight"
bmi_cat[!is.na(bmi) & bmi >= 25 & bmi < 30] <- "overweight"
bmi_cat[!is.na(bmi) & bmi >= 30] <- "obesity"

out <- data.frame(
  person_id = as.character(df$NHISPID),
  year = num(df$YEAR),
  survey_year = num(df$YEAR),
  sample_adult = as.integer(num(df$ASTATFLG) == 1),
  adult_18plus = as.integer(age >= 18),
  adult_20plus = as.integer(age >= 20),
  mortality_linkage_eligible = as.integer(num(df$MORTELIG) == 1),
  died_allcause = died,
  followup_time_months = fu$value,
  followup_time_years = fu$value / 12,
  msa_days_week = msa_days,
  msa_cat5 = msa_cat,
  msa_cat5_label = c("0 days/week", "1 day/week", "2 days/week", "3-4 days/week", "5+ days/week")[msa_cat + 1],
  msa_guideline = ifelse(!is.na(msa_days), as.integer(msa_days >= 2), NA),
  insufficient_msa = ifelse(!is.na(msa_days), as.integer(msa_days < 2), NA),
  aerobic_minutes_meq_weekly = aerobic,
  aerobic_meets_guideline = ifelse(!is.na(aerobic), as.integer(aerobic >= 150), NA),
  aerobic_guideline = ifelse(!is.na(aerobic), as.integer(aerobic >= 150), NA),
  aerobic_category = aerobic_category,
  age = age,
  age_cat = age_group_18plus(age),
  age_group = age_group_18plus(age),
  sex = sex_label(df$SEX),
  race_ethnicity = race_ethnicity(df),
  education = if ("EDUC" %in% names(df)) educ_cat(df$EDUC) else NA_character_,
  poverty = if ("POVERTY" %in% names(df)) poverty_cat(df$POVERTY) else NA_character_,
  marital_status = if ("MARSTAT" %in% names(df)) as.character(df$MARSTAT) else NA_character_,
  region = if ("REGION" %in% names(df)) region_label(df$REGION) else NA_character_,
  bmi = bmi,
  bmi_cat = bmi_cat,
  smoking_status = if ("SMOKESTATUS2" %in% names(df)) as.character(df$SMOKESTATUS2) else NA_character_,
  alcohol_use = if ("ALCSTAT1" %in% names(df)) as.character(df$ALCSTAT1) else NA_character_,
  self_rated_health = if ("HEALTH" %in% names(df)) as.character(df$HEALTH) else NA_character_,
  diabetes = if ("DIABETICEV" %in% names(df)) binary_codes(df$DIABETICEV) else NA_real_,
  hypertension = if ("HYPERTENEV" %in% names(df)) binary_codes(df$HYPERTENEV) else NA_real_,
  cvd_history = cvd_history,
  cancer_history = if ("CANCEREV" %in% names(df)) binary_codes(df$CANCEREV) else NA_real_,
  weight_mortality = ifelse(num(df$MORTWTSA) > 0, num(df$MORTWTSA), NA),
  weight_sample_adult = if ("SAMPWEIGHT" %in% names(df)) ifelse(num(df$SAMPWEIGHT) > 0, num(df$SAMPWEIGHT), NA) else NA_real_,
  strata = if ("STRATA" %in% names(df)) num(df$STRATA) else NA_real_,
  psu = if ("PSU" %in% names(df)) num(df$PSU) else NA_real_,
  stringsAsFactors = FALSE
)
out$combined_guideline <- ifelse(
  is.na(out$msa_guideline) | is.na(out$aerobic_meets_guideline),
  NA_character_,
  ifelse(out$msa_guideline == 1 & out$aerobic_meets_guideline == 1, "both guidelines",
    ifelse(out$msa_guideline == 1, "MSA only",
      ifelse(out$aerobic_meets_guideline == 1, "aerobic only", "neither guideline")
    )
  )
)
out$combined_pa_guideline <- out$combined_guideline
out$nonmissing_msa <- as.integer(!is.na(out$msa_days_week))
out$nonmissing_followup <- as.integer(!is.na(out$followup_time_months) & !is.na(out$died_allcause))
complete_vars <- c("adult_18plus", "sample_adult", "mortality_linkage_eligible", "nonmissing_followup", "nonmissing_msa", "followup_time_years", "died_allcause", "msa_cat5", "aerobic_category", "age", "sex", "race_ethnicity", "education", "poverty", "marital_status", "smoking_status", "alcohol_use", "bmi_cat", "self_rated_health", "diabetes", "hypertension", "cvd_history", "cancer_history", "weight_mortality", "strata", "psu")
out$complete_case_main <- as.integer(stats::complete.cases(out[, complete_vars]))
out$lag24_exclusion <- as.integer(out$died_allcause == 1 & out$followup_time_months <= 24)
out$complete_case_lag24 <- as.integer(out$complete_case_main == 1 & (is.na(out$lag24_exclusion) | out$lag24_exclusion == 0))

main <- out[out$complete_case_main == 1, ]
lag24 <- out[out$complete_case_lag24 == 1, ]
write_csv(out, file.path(processed_dir, "msa_survival_full.csv"))
write_csv(main, file.path(processed_dir, "msa_survival_main_completecase.csv"))
write_csv(lag24, file.path(processed_dir, "msa_survival_lag24_completecase.csv"))
write_stata_optional(out, file.path(processed_dir, "msa_survival_full.dta"))
write_stata_optional(main, file.path(processed_dir, "msa_survival_main_completecase.dta"))
write_stata_optional(lag24, file.path(processed_dir, "msa_survival_lag24_completecase.dta"))

dictionary <- data.frame(
  variable_name = names(out),
  description = names(out),
  source_variables = "",
  coding = "",
  missing_values = "",
  notes = "",
  stringsAsFactors = FALSE
)
write_csv(dictionary, file.path(processed_dir, "msa_variable_dictionary.csv"))
flow <- data.frame(
  step = c("raw_rows", "adult_sample_linked_rows", "main_complete_case", "lag24_complete_case"),
  n = c(nrow(out), sum(out$adult_18plus == 1 & out$sample_adult == 1 & out$mortality_linkage_eligible == 1, na.rm = TRUE), nrow(main), nrow(lag24))
)
write_csv(flow, file.path(processed_dir, "msa_sample_flow.csv"))
write_text(here("outputs", "logs", "variable_availability_report.md"), paste(c(
  "# Variable Availability Report",
  "",
  paste0("Generated: ", stamp()),
  "",
  paste0("Raw input: `", rel_path(path), "`."),
  paste0("Follow-up source: `", fu$source, "`. ", fu$note),
  "",
  "The R build script constructs the same canonical processed filenames used by the Stata and R downstream workflow."
), collapse = "\n"))
message("Built processed NHIS-LMF survival datasets.")
