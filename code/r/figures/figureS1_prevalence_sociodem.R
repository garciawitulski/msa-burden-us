## Figure S1. Prevalence of insufficient MSA by sociodemographic stratum.

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
  mutate(prevalence_insufficient_pct = prevalence_insufficient_msa * 100)

build_panel <- function(domain_label, sociodem_var, level_order = NULL,
                         title_letter, x_max = 90) {
  d <- dat %>% filter(sociodemographic_variable == sociodem_var)
  if (!is.null(level_order)) {
    d <- d %>% mutate(group_value = factor(group_value, levels = level_order))
  } else {
    d <- d %>% mutate(group_value = fct_reorder(group_value, prevalence_insufficient_pct))
  }
  ggplot(d, aes(y = group_value, x = prevalence_insufficient_pct)) +
    geom_col(fill = unname(okabe_ito["sky_blue"]), width = 0.7, alpha = 0.9) +
    geom_text(aes(label = sprintf("%.1f", prevalence_insufficient_pct)),
              hjust = -0.15, size = 2.8, color = "grey15") +
    scale_x_continuous(limits = c(0, x_max),
                       labels = function(x) paste0(x, "%")) +
    labs(y = NULL, x = "Insufficient MSA, %",
         subtitle = paste0("(", title_letter, ") ", domain_label)) +
    theme_paper() +
    theme(panel.grid.major.x = element_line(color = "grey90"),
          panel.grid.major.y = element_blank())
}

edu_levels <- c("Less than high school", "High school/GED", "Some college/AA",
                "Bachelor's degree", "Graduate/professional degree")
pov_levels <- c("<1.00 poverty ratio", "1.00-1.99 poverty ratio",
                ">=2.00 poverty ratio")
reg_levels <- c("Northeast", "Midwest", "South", "West")

p1 <- build_panel("Race or ethnicity", "race_ethnicity", title_letter = "a")
p2 <- build_panel("Education",         "education",      level_order = edu_levels, title_letter = "b")
p3 <- build_panel("Poverty-income ratio", "poverty",     level_order = pov_levels, title_letter = "c")
p4 <- build_panel("Census region",      "region",        level_order = reg_levels, title_letter = "d")

p <- (p1 | p2) / (p3 | p4)

save_figure(p, "figureS1_prevalence_sociodem", width_in = 8.2, height_in = 6.8)
message("Wrote figureS1_prevalence_sociodem.{pdf,png}")
