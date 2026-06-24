## Supplementary Figure S4. Prevalence of insufficient MSA by sociodemographic stratum.

suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
  library(ggplot2)
  library(patchwork)
  library(forcats)
  library(scales)
})
source(file.path("code", "r", "figures", "theme_paper.R"))

dat <- read_csv(
  file.path("outputs", "tables",
            "nhis_2024_msa_prevalence_premature_30_69_by_sociodemographics.csv"),
  show_col_types = FALSE
) %>%
  mutate(prev_pct = prevalence_insufficient_msa * 100)

build_panel <- function(domain_label, sociodem_var, level_order = NULL,
                         title_letter, x_max = 100) {
  d <- dat %>% filter(sociodemographic_variable == sociodem_var)
  if (!is.null(level_order)) {
    d <- d %>% mutate(group_value = factor(group_value, levels = rev(level_order)))
  } else {
    d <- d %>% mutate(group_value = fct_reorder(group_value, prev_pct))
  }
  ggplot(d, aes(y = group_value, x = prev_pct)) +
    geom_col(fill = unname(lancet_palette["navy"]), width = 0.62,
             color = "black", linewidth = 0.25) +
    geom_text(aes(label = sprintf("%.1f", prev_pct)), hjust = -0.12,
              size = 2.5, color = "black") +
    scale_x_continuous(limits = c(0, x_max), breaks = seq(0, 80, 20),
                       labels = function(x) paste0(x, "%"),
                       expand = c(0, 0)) +
    labs(y = NULL, x = "Insufficient MSA (%)", tag = title_letter) +
    theme_paper() +
    theme(axis.line.y = element_blank(), axis.ticks.y = element_blank())
}

edu_levels <- c("Less than high school", "High school/GED", "Some college/AA",
                "Bachelor's degree", "Graduate/professional degree")
pov_levels <- c("<1.00 poverty ratio", "1.00-1.99 poverty ratio",
                ">=2.00 poverty ratio")
reg_levels <- c("Northeast", "Midwest", "South", "West")

p1 <- build_panel("Race or ethnicity",     "race_ethnicity", title_letter = "A")
p2 <- build_panel("Education",             "education",      level_order = edu_levels, title_letter = "B")
p3 <- build_panel("Poverty-income ratio",  "poverty",        level_order = pov_levels, title_letter = "C")
p4 <- build_panel("Census region",         "region",         level_order = reg_levels, title_letter = "D")

p <- (p1 | p2) / (p3 | p4)

save_figure(p, "figureS4_prevalence_sociodem", width_in = 7.2, height_in = 5.6)
message("Wrote figureS4_prevalence_sociodem.{pdf,png}")
