source(file.path("code", "r", "lib", "msaburden.R"))

ensure_standard_dirs()

required_packages <- c("haven", "foreign")
optional_packages <- c("jsonlite", "httr", "readxl", "xml2")
status <- data.frame(
  package = c(required_packages, optional_packages),
  role = c(rep("required_or_fallback_for_stata_io", length(required_packages)), rep("optional_external_io", length(optional_packages))),
  status = ifelse(vapply(c(required_packages, optional_packages), requireNamespace, logical(1), quietly = TRUE), "installed", "missing"),
  stringsAsFactors = FALSE
)
write_csv(status, here("outputs", "logs", "r_package_status.csv"))

lines <- c(
  "# Project Setup Log",
  "",
  paste0("Generated: ", stamp()),
  "",
  "Created standard data, output, and documentation directories.",
  "",
  "Package status is written to `outputs/logs/r_package_status.csv`.",
  "",
  "The workflow is R/Stata-only. External API steps fall back to documented manual instructions if optional R packages or credentials are unavailable."
)
write_text(here("outputs", "logs", "setup_log.md"), paste(lines, collapse = "\n"))
message("Project folders and package-status log are ready.")
