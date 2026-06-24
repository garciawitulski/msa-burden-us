source(file.path("code", "r", "lib", "msaburden.R"))

ensure_standard_dirs()
df <- read_csv_required(here("data", "processed", "msa_survival_main_completecase.csv"))
out_dir <- here("outputs", "tables", "manuscript")
ensure_dir(out_dir)

groups <- list(
  Overall = rep(TRUE, nrow(df)),
  Insufficient = num(df$insufficient_msa) == 1,
  Meets = num(df$insufficient_msa) == 0
)

rows <- list()
for (g in names(groups)) {
  sub <- df[groups[[g]] %in% TRUE, ]
  rows[[length(rows) + 1]] <- data.frame(characteristic = "N", group = g, value = fmt_int(nrow(sub)))
  rows[[length(rows) + 1]] <- data.frame(characteristic = "Age, mean (SD)", group = g, value = paste0(fmt_float(weighted_mean(sub$age, sub$weight_mortality), 1), " (", fmt_float(weighted_sd(sub$age, sub$weight_mortality), 1), ")"))
  rows[[length(rows) + 1]] <- data.frame(characteristic = "Female, weighted %", group = g, value = fmt_pct(weighted_mean(as.integer(sub$sex == "Female"), sub$weight_mortality), 1))
}
table1 <- do.call(rbind, rows)
write_csv(table1, file.path(out_dir, "table1_msa_descriptive_by_exposure.csv"))
tex_lines <- c(
  "\\begin{tabular}{lll}",
  "\\toprule",
  "Characteristic & Group & Value \\\\",
  "\\midrule",
  paste0(apply(table1, 1, function(x) paste(x, collapse = " & ")), " \\\\"),
  "\\bottomrule",
  "\\end{tabular}"
)
write_text(here("manuscript_latex", "tables", "table1_msa_descriptive_by_exposure.tex"), paste(tex_lines, collapse = "\n"))
message("Built Table 1 descriptive outputs.")
