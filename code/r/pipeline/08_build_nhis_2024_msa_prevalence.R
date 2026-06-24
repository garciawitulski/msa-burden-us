source(file.path("code", "r", "lib", "msaburden.R"))

ensure_standard_dirs()
raw_dir <- here("data", "raw", "nhis_2024")
processed_dir <- here("data", "processed", "nhis_2024")
ensure_dir(processed_dir)

csv_from_zip <- function(path) {
  listing <- utils::unzip(path, list = TRUE)
  csv <- listing$Name[grepl("\\.csv$", listing$Name, ignore.case = TRUE)][1]
  if (is.na(csv)) stop_issue("NHIS 2024 zip missing CSV", paste0("`", rel_path(path), "` contains no CSV."))
  con <- unz(path, csv)
  on.exit(close(con), add = TRUE)
  read.csv(con, stringsAsFactors = FALSE, check.names = FALSE)
}

detect_input <- function() {
  paths <- c(list.files(raw_dir, pattern = "\\.csv(\\.gz)?$", full.names = TRUE), list.files(raw_dir, pattern = "\\.zip$", full.names = TRUE))
  for (p in paths) {
    header <- if (grepl("\\.zip$", p, ignore.case = TRUE)) names(csv_from_zip(p)) else names(read.csv(p, nrows = 1, check.names = FALSE))
    upper <- toupper(header)
    if (all(c("YEAR", "SAMPWEIGHT", "AGE", "SEX", "STRONGFWK") %in% upper)) return(list(source = "ipums", path = p))
    if (all(c("SRVY_YR", "WTFA_A", "AGEP_A", "SEX_A", "STRFREQW_A") %in% upper)) return(list(source = "cdc", path = p))
  }
  stop_issue("NHIS 2024 input not found", "No usable IPUMS or CDC NHIS 2024 Sample Adult file was found in `data/raw/nhis_2024/`.")
}

clean_ipums_freq <- function(x) {
  x <- num(x)
  out <- rep(NA_real_, length(x))
  out[x == 95] <- 0
  out[x == 94] <- 0.5
  out[x >= 1 & x <= 92] <- x[x >= 1 & x <= 92]
  out
}

clean_cdc_freq <- function(x) {
  x <- num(x)
  out <- rep(NA_real_, length(x))
  out[x == 94] <- 0
  out[x == 0] <- 0.5
  out[x >= 1 & x <= 28] <- x[x >= 1 & x <= 28]
  out
}

weighted_prev <- function(df, groups, table_name) {
  if (!length(groups)) {
    split_list <- list(all = df)
    keys <- data.frame(group = "overall", group_value = "all")
  } else {
    split_list <- split(df, df[groups], drop = TRUE)
    key_parts <- do.call(rbind, strsplit(names(split_list), "\\."))
    keys <- as.data.frame(key_parts, stringsAsFactors = FALSE)
    names(keys) <- groups
  }
  rows <- lapply(seq_along(split_list), function(i) {
    sub <- split_list[[i]]
    w <- num(sub$weight_sample_adult)
    ok <- is.finite(w) & w > 0 & !is.na(sub$insufficient_msa_2024)
    sub <- sub[ok, ]
    w <- w[ok]
    meets <- num(sub$msa_guideline_2024)
    insuff <- num(sub$insufficient_msa_2024)
    row <- data.frame(
      table = table_name,
      n_unweighted = nrow(sub),
      weighted_total = sum(w),
      weighted_meets_msa_guideline = sum(w * meets, na.rm = TRUE),
      weighted_insufficient_msa = sum(w * insuff, na.rm = TRUE),
      prevalence_meets_msa_guideline = sum(w * meets, na.rm = TRUE) / sum(w),
      prevalence_insufficient_msa = sum(w * insuff, na.rm = TRUE) / sum(w),
      stringsAsFactors = FALSE
    )
    if (!length(groups)) cbind(row, group = "overall", group_value = "all") else cbind(row, keys[i, , drop = FALSE])
  })
  do.call(rbind, rows)
}

input <- detect_input()
df <- if (grepl("\\.zip$", input$path, ignore.case = TRUE)) csv_from_zip(input$path) else read.csv(input$path, stringsAsFactors = FALSE, check.names = FALSE)
names(df) <- toupper(names(df))

if (input$source == "ipums") {
  age <- num(df$AGE)
  strong <- clean_ipums_freq(df$STRONGFWK)
  out <- data.frame(
    source = "ipums", survey_year = num(df$YEAR), person_id = if ("NHISPID" %in% names(df)) as.character(df$NHISPID) else seq_len(nrow(df)),
    sample_adult = if ("ASTATFLG" %in% names(df)) as.integer(num(df$ASTATFLG) == 1) else 1,
    weight_sample_adult = num(df$SAMPWEIGHT), strata = if ("STRATA" %in% names(df)) num(df$STRATA) else NA,
    psu = if ("PSU" %in% names(df)) num(df$PSU) else NA, age = age, age_group = age_group_18plus(age),
    sex = sex_label(df$SEX), race_ethnicity = NA_character_, education = NA_character_, poverty = NA_character_,
    region = if ("REGION" %in% names(df)) region_label(df$REGION) else NA_character_,
    msa_times_week_2024 = strong, src_strength_frequency = num(df$STRONGFWK), stringsAsFactors = FALSE
  )
} else {
  age <- num(df$AGEP_A)
  strong <- clean_cdc_freq(df$STRFREQW_A)
  out <- data.frame(
    source = "cdc", survey_year = num(df$SRVY_YR), person_id = if ("HHX" %in% names(df)) as.character(df$HHX) else seq_len(nrow(df)),
    sample_adult = if ("HHSTAT_A" %in% names(df)) as.integer(num(df$HHSTAT_A) == 1) else 1,
    weight_sample_adult = num(df$WTFA_A), strata = if ("PSTRAT" %in% names(df)) num(df$PSTRAT) else NA,
    psu = if ("PPSU" %in% names(df)) num(df$PPSU) else NA, age = age, age_group = age_group_18plus(age),
    sex = sex_label(df$SEX_A), race_ethnicity = if ("HISPALLP_A" %in% names(df)) as.character(df$HISPALLP_A) else NA_character_,
    education = if ("EDUCP_A" %in% names(df)) as.character(df$EDUCP_A) else NA_character_,
    poverty = if ("RATCAT_A" %in% names(df)) as.character(df$RATCAT_A) else NA_character_,
    region = if ("REGION" %in% names(df)) region_label(df$REGION) else NA_character_,
    msa_times_week_2024 = strong, src_strength_frequency = num(df$STRFREQW_A), stringsAsFactors = FALSE
  )
}
out$msa_guideline_2024 <- ifelse(!is.na(out$msa_times_week_2024), as.integer(out$msa_times_week_2024 >= 2), NA)
out$insufficient_msa_2024 <- ifelse(!is.na(out$msa_times_week_2024), as.integer(out$msa_times_week_2024 < 2), NA)
out$nonmissing_msa_2024 <- as.integer(!is.na(out$msa_times_week_2024))
out$adult_18plus <- as.integer(out$age >= 18)
out$adult_30_69 <- as.integer(out$age >= 30 & out$age <= 69)
out$age_group_premature_30_69 <- age_group_30_69(out$age)

write_csv(out, file.path(processed_dir, "nhis_2024_msa_prevalence_dataset.csv"))
write_stata_optional(out, file.path(processed_dir, "nhis_2024_msa_prevalence_dataset.dta"))

eligible <- out[out$adult_18plus == 1 & out$sample_adult == 1, ]
write_csv(weighted_prev(eligible, character(), "overall"), here("outputs", "tables", "nhis_2024_msa_prevalence_overall.csv"))
write_csv(weighted_prev(eligible, "sex", "sex"), here("outputs", "tables", "nhis_2024_msa_prevalence_by_sex.csv"))
write_csv(weighted_prev(eligible, "age_group", "age_group"), here("outputs", "tables", "nhis_2024_msa_prevalence_by_age.csv"))
write_csv(weighted_prev(eligible, c("age_group", "sex"), "age_group_sex"), here("outputs", "tables", "nhis_2024_msa_prevalence_by_age_sex.csv"))

prem <- out[out$adult_30_69 == 1 & out$sample_adult == 1 & !is.na(out$age_group_premature_30_69), ]
prem$age_group <- prem$age_group_premature_30_69
add_meta <- function(x) cbind(analysis_population = "premature_30_69", age_range = "30-69", denominator = "NHIS 2024 sample adults aged 30-69 with nonmissing MSA and positive sample adult weight", weight = "weight_sample_adult", x)
write_csv(add_meta(weighted_prev(prem, character(), "premature_30_69_overall")), here("outputs", "tables", "nhis_2024_msa_prevalence_premature_30_69_overall.csv"))
write_csv(add_meta(weighted_prev(prem, "sex", "premature_30_69_sex")), here("outputs", "tables", "nhis_2024_msa_prevalence_premature_30_69_by_sex.csv"))
write_csv(add_meta(weighted_prev(prem, "age_group", "premature_30_69_age_group")), here("outputs", "tables", "nhis_2024_msa_prevalence_premature_30_69_by_age.csv"))
write_csv(add_meta(weighted_prev(prem, c("age_group", "sex"), "premature_30_69_age_group_sex")), here("outputs", "tables", "nhis_2024_msa_prevalence_premature_30_69_by_age_sex.csv"))
write_text(here("outputs", "logs", "nhis_2024_prevalence_quality_checks.md"), paste(c(
  "# NHIS 2024 Prevalence Quality Checks",
  "",
  paste0("Generated: ", stamp()),
  paste0("- Source: `", input$source, "`."),
  paste0("- Data file: `", rel_path(input$path), "`."),
  paste0("- Processed rows: ", nrow(out), "."),
  paste0("- Adult 30-69 rows: ", nrow(prem), ".")
), collapse = "\n"))
message("Built NHIS 2024 prevalence outputs.")
