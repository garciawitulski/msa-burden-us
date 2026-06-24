source(file.path("code", "r", "lib", "msaburden.R"))

ensure_standard_dirs()
raw_dir <- here("data", "raw", "nhis_2024")
interim_dir <- here("data", "interim", "nhis_2024")
ensure_dir(raw_dir)
ensure_dir(interim_dir)

files <- c(
  adult_csv_zip = "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Datasets/NHIS/2024/adult24csv.zip",
  adult_codebook_pdf = "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Dataset_Documentation/NHIS/2024/adult-codebook.pdf",
  adult_summary_pdf = "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Dataset_Documentation/NHIS/2024/adult-summary.pdf",
  adult_stata_zip = "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Datasets/NHIS/2024/adult24stata.zip",
  metadata_xml = "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Dataset_Documentation/NHIS/2024/adult-metadata.xml"
)
log_lines <- c(paste0("NHIS 2024 download started: ", stamp()))
ok <- TRUE
for (label in names(files)) {
  url <- files[[label]]
  dest <- file.path(raw_dir, basename(url))
  if (file.exists(dest) && file.info(dest)$size > 0) {
    log_lines <- c(log_lines, paste("Using cached", rel_path(dest)))
    next
  }
  result <- try(utils::download.file(url, destfile = dest, mode = "wb", quiet = TRUE), silent = TRUE)
  if (inherits(result, "try-error")) {
    ok <- FALSE
    log_lines <- c(log_lines, paste("Download failed", label, url))
  } else {
    log_lines <- c(log_lines, paste("Downloaded", rel_path(dest)))
  }
}
write_text(here("outputs", "logs", "07_download_nhis_2024_prevalence.log"), paste(log_lines, collapse = "\n"))
write_text(file.path(interim_dir, "nhis_2024_download_metadata.txt"), paste(c(
  paste0("Generated: ", stamp()),
  "Source: CDC/NCHS 2024 NHIS public-use Sample Adult files.",
  paste(names(files), files, sep = ": ")
), collapse = "\n"))
if (!ok) {
  append_issue_once("NHIS 2024 automatic download incomplete", "One or more CDC/NCHS NHIS 2024 files could not be downloaded automatically. Manual instructions were written to `docs/NHIS_2024_download_instructions.md`.")
  write_text(here("docs", "NHIS_2024_download_instructions.md"), paste(c(
    "# NHIS 2024 Download Instructions",
    "",
    "Download the 2024 Sample Adult public-use files from:",
    "",
    "https://www.cdc.gov/nchs/nhis/documentation/2024-nhis.html",
    "",
    "Place `adult24csv.zip` and documentation files in `data/raw/nhis_2024/`."
  ), collapse = "\n"))
}
message("NHIS 2024 download step complete.")
