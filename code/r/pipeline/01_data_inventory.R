source(file.path("code", "r", "lib", "msaburden.R"))

ensure_standard_dirs()
roots <- c(here("data", "raw"), here("data", "external"))
files <- unlist(lapply(roots, function(p) if (dir.exists(p)) list.files(p, recursive = TRUE, full.names = TRUE) else character()))

classify <- function(path) {
  low <- tolower(path)
  if (grepl("\\.(xml|cbk|do|sas|sps|json|txt|md|pdf)$", low)) return("metadata_or_documentation")
  if (grepl("\\.(csv|gz|dta|dat|sav|por|parquet|feather|xlsx|zip)$", low)) return("data_or_archive")
  "other"
}

inventory <- data.frame(
  path = rel_path(files),
  name = basename(files),
  extension = tools::file_ext(files),
  bytes = file.info(files)$size,
  modified = as.character(file.info(files)$mtime),
  role = vapply(files, classify, character(1)),
  stringsAsFactors = FALSE
)
write_csv(inventory, here("outputs", "logs", "raw_external_data_inventory.csv"))

summary <- aggregate(path ~ role, inventory, length)
names(summary) <- c("role", "n_files")
write_csv(summary, here("outputs", "logs", "raw_external_data_inventory_summary.csv"))
message("Wrote raw/external data inventory.")
