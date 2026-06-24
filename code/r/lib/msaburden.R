## Shared helpers for the MSA burden US R/Stata pipeline.

project_root <- function() {
  normalizePath(getwd(), winslash = "/", mustWork = TRUE)
}

here <- function(...) {
  file.path(project_root(), ...)
}

ensure_dir <- function(path) {
  if (!dir.exists(path)) dir.create(path, recursive = TRUE, showWarnings = FALSE)
  invisible(path)
}

ensure_standard_dirs <- function() {
  invisible(lapply(
    c(
      here("data", "raw"),
      here("data", "interim"),
      here("data", "processed"),
      here("data", "external"),
      here("docs"),
      here("outputs", "logs"),
      here("outputs", "tables"),
      here("outputs", "figures"),
      here("outputs", "figures", "manuscript")
    ),
    ensure_dir
  ))
}

stamp <- function() format(Sys.time(), "%Y-%m-%dT%H:%M:%S")

rel_path <- function(path) {
  root <- paste0(project_root(), "/")
  sub(root, "", normalizePath(path, winslash = "/", mustWork = FALSE), fixed = TRUE)
}

write_text <- function(path, text) {
  ensure_dir(dirname(path))
  writeLines(text, path, useBytes = TRUE)
  invisible(path)
}

append_issue_once <- function(title, message) {
  ensure_standard_dirs()
  path <- here("outputs", "logs", "issues_to_resolve.md")
  old <- if (file.exists(path)) paste(readLines(path, warn = FALSE), collapse = "\n") else "# Issues to Resolve\n"
  if (grepl(title, old, fixed = TRUE)) return(invisible(FALSE))
  block <- paste0("\n\n## ", stamp(), " - ", title, "\n\n", trimws(message), "\n")
  write_text(path, paste0(trimws(old), block))
  invisible(TRUE)
}

stop_issue <- function(title, message) {
  append_issue_once(title, message)
  stop(message, call. = FALSE)
}

require_columns <- function(df, required, path = "input") {
  missing <- setdiff(required, names(df))
  if (length(missing)) {
    stop_issue("Input missing required columns", paste0("`", path, "` is missing: ", paste(missing, collapse = ", "), "."))
  }
  invisible(TRUE)
}

read_csv_required <- function(path, required = NULL, ...) {
  if (!file.exists(path)) stop_issue("Missing required input", paste0("Required input not found: `", rel_path(path), "`."))
  df <- read.csv(path, stringsAsFactors = FALSE, check.names = FALSE, ...)
  if (!is.null(required)) require_columns(df, required, rel_path(path))
  df
}

write_csv <- function(df, path) {
  ensure_dir(dirname(path))
  utils::write.csv(df, path, row.names = FALSE, na = "")
  invisible(path)
}

num <- function(x) suppressWarnings(as.numeric(x))

first_existing <- function(cols, candidates) {
  upper <- toupper(cols)
  for (candidate in candidates) {
    hit <- match(toupper(candidate), upper)
    if (!is.na(hit)) return(cols[[hit]])
  }
  NULL
}

weighted_mean <- function(values, weights) {
  values <- num(values)
  weights <- num(weights)
  ok <- is.finite(values) & is.finite(weights) & weights > 0
  if (!any(ok)) return(NA_real_)
  sum(values[ok] * weights[ok]) / sum(weights[ok])
}

weighted_sd <- function(values, weights) {
  values <- num(values)
  weights <- num(weights)
  ok <- is.finite(values) & is.finite(weights) & weights > 0
  if (sum(ok) <= 1) return(NA_real_)
  mu <- weighted_mean(values[ok], weights[ok])
  sqrt(sum(weights[ok] * (values[ok] - mu)^2) / sum(weights[ok]))
}

weighted_median <- function(values, weights) {
  values <- num(values)
  weights <- num(weights)
  ok <- is.finite(values) & is.finite(weights) & weights > 0
  if (!any(ok)) return(NA_real_)
  values <- values[ok]
  weights <- weights[ok]
  ord <- order(values)
  values <- values[ord]
  weights <- weights[ord]
  values[which(cumsum(weights) >= sum(weights) / 2)[1]]
}

fmt_int <- function(x) ifelse(is.na(num(x)), "", format(round(num(x)), big.mark = ",", scientific = FALSE))
fmt_float <- function(x, digits = 2) ifelse(is.na(num(x)), "", formatC(num(x), format = "f", digits = digits))
fmt_pct <- function(x, digits = 1) ifelse(is.na(num(x)), "", formatC(100 * num(x), format = "f", digits = digits))
fmt_money <- function(x) paste0("US\\$", fmt_int(x))

markdown_table <- function(df, title, note = NULL) {
  if (!nrow(df)) {
    body <- "_No rows._"
  } else {
    header <- paste0("| ", paste(names(df), collapse = " | "), " |")
    sep <- paste0("|", paste(rep("---", ncol(df)), collapse = "|"), "|")
    rows <- apply(df, 1, function(row) paste0("| ", paste(gsub("\\|", "\\\\|", as.character(row)), collapse = " | "), " |"))
    body <- paste(c(header, sep, rows), collapse = "\n")
  }
  paste(c(paste0("# ", title), "", body, if (!is.null(note)) c("", paste0("_Note: ", note, "_"))), collapse = "\n")
}

save_table <- function(df, csv_path, md_path, title, note = NULL) {
  write_csv(df, csv_path)
  write_text(md_path, markdown_table(df, title, note))
}

paf_value <- function(prevalence, hr) {
  prevalence * (hr - 1) / (1 + prevalence * (hr - 1))
}

simulate_paf <- function(prevalence, hr, ci_lower, ci_upper, n_draws = 10000L, seed = 20260429L) {
  set.seed(seed)
  se <- (log(ci_upper) - log(ci_lower)) / (2 * 1.96)
  draws <- exp(rnorm(n_draws, mean = log(hr), sd = se))
  paf_value(prevalence, draws)
}

draw_summary <- function(x) {
  c(
    median = as.numeric(stats::median(x, na.rm = TRUE)),
    p2_5 = as.numeric(stats::quantile(x, 0.025, na.rm = TRUE, names = FALSE)),
    p97_5 = as.numeric(stats::quantile(x, 0.975, na.rm = TRUE, names = FALSE))
  )
}

age_group_18plus <- function(age) {
  age <- num(age)
  out <- rep(NA_character_, length(age))
  out[age >= 18 & age <= 34] <- "18-34"
  out[age >= 35 & age <= 44] <- "35-44"
  out[age >= 45 & age <= 54] <- "45-54"
  out[age >= 55 & age <= 64] <- "55-64"
  out[age >= 65 & age <= 74] <- "65-74"
  out[age >= 75] <- "75+"
  out
}

age_group_30_69 <- function(age) {
  age <- num(age)
  out <- rep(NA_character_, length(age))
  out[age >= 30 & age <= 34] <- "30-34"
  out[age >= 35 & age <= 44] <- "35-44"
  out[age >= 45 & age <= 54] <- "45-54"
  out[age >= 55 & age <= 64] <- "55-64"
  out[age >= 65 & age <= 69] <- "65-69"
  out
}

sex_label <- function(x) {
  out <- rep(NA_character_, length(x))
  out[num(x) == 1] <- "Male"
  out[num(x) == 2] <- "Female"
  out
}

region_label <- function(x) {
  labels <- c("1" = "Northeast", "2" = "Midwest", "3" = "South", "4" = "West")
  unname(labels[as.character(num(x))])
}

write_stata_optional <- function(df, path) {
  ensure_dir(dirname(path))
  if (requireNamespace("haven", quietly = TRUE)) {
    haven::write_dta(df, path)
    return(invisible(TRUE))
  }
  if (requireNamespace("foreign", quietly = TRUE)) {
    foreign::write.dta(df, path)
    return(invisible(TRUE))
  }
  append_issue_once("Stata export unavailable", paste0("Could not write `", rel_path(path), "` because neither the R package `haven` nor `foreign` is available. CSV output was still created."))
  invisible(FALSE)
}

replace_marked_section <- function(path, title, content) {
  start <- paste0("<!-- BEGIN ", title, " -->")
  end <- paste0("<!-- END ", title, " -->")
  old <- if (file.exists(path)) paste(readLines(path, warn = FALSE), collapse = "\n") else ""
  block <- paste0(start, "\n", trimws(content), "\n", end)
  pattern <- paste0(start, "(.|\n)*?", end)
  if (grepl(start, old, fixed = TRUE)) {
    new <- sub(pattern, block, old, perl = TRUE)
  } else {
    new <- paste0(trimws(old), "\n\n", block)
  }
  write_text(path, new)
}

present_value_factor <- function(years, discount_rate) {
  years <- num(years)
  ifelse(
    is.na(years) | years <= 0,
    0,
    ifelse(discount_rate == 0, years, (1 - (1 + discount_rate)^(-years)) / discount_rate)
  )
}
