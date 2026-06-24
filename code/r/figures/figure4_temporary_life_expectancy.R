## Figure 4. Temporary life expectancy from age 30 to 70: observed vs counterfactual,
## total and by sex (slope-style with annotated differences).

suppressPackageStartupMessages({
  library(dplyr)
  library(tidyr)
  library(readr)
  library(ggplot2)
})
source(file.path("code", "r", "figures", "theme_paper.R"))

tle <- read_csv(
  file.path("outputs", "tables",
            "msa_life_expectancy_gain_premature_30_69_nhis2024.csv"),
  show_col_types = FALSE
)

mc <- read_csv(
  file.path("outputs", "tables",
            "msa_life_expectancy_gain_montecarlo_premature_30_69_nhis2024.csv"),
  show_col_types = FALSE
) %>%
  select(sex,
         gain_lo = gain_temporary_life_expectancy_30_70_p2_5,
         gain_hi = gain_temporary_life_expectancy_30_70_p97_5)

dat <- tle %>%
  select(sex,
         observed = observed_temporary_life_expectancy_30_70,
         counterfactual = counterfactual_temporary_life_expectancy_30_70,
         gain = gain_temporary_life_expectancy_30_70) %>%
  left_join(mc, by = "sex") %>%
  mutate(group = case_when(
    sex == "All" ~ "All adults",
    TRUE ~ sex
  )) %>%
  mutate(group = factor(group, levels = c("All adults", "Female", "Male")))

long <- dat %>%
  pivot_longer(c(observed, counterfactual),
               names_to = "scenario", values_to = "tle") %>%
  mutate(scenario = factor(scenario, levels = c("observed", "counterfactual"),
                           labels = c("Observed", "Counterfactual")))

annot <- dat %>%
  mutate(label = sprintf("Δ = +%.3f\n(UI %.3f–%.3f)", gain, gain_lo, gain_hi),
         x_lab = 2.4)

x_levels <- c("Observed", "Counterfactual")
long$xpos <- as.numeric(long$scenario)

p <- ggplot() +
  geom_segment(data = dat,
               aes(x = 1, xend = 2, y = observed, yend = counterfactual,
                   color = group),
               linewidth = 0.7) +
  geom_point(data = long, aes(x = xpos, y = tle, color = group), size = 2.6) +
  geom_text(data = annot, aes(x = x_lab, y = (observed + counterfactual) / 2,
                              label = label, color = group),
            size = 2.8, hjust = 0, lineheight = 0.95) +
  scale_x_continuous(breaks = c(1, 2), labels = c("Observed", "Counterfactual"),
                     limits = c(0.7, 3.5)) +
  scale_y_continuous(limits = c(36.4, 38.4), breaks = seq(36.5, 38.5, 0.5)) +
  scale_color_manual(values = c(
    "All adults" = unname(okabe_ito["black"]),
    "Female"     = unname(sex_palette["Female"]),
    "Male"       = unname(sex_palette["Male"])
  ), name = NULL) +
  labs(x = NULL,
       y = "Temporary life expectancy, ages 30–70 (years)",
       caption = "Y-axis truncated to highlight the difference; differences are within 95% UI from HR uncertainty.") +
  theme_paper() +
  theme(legend.position = "top",
        panel.grid.major.y = element_line(color = "grey90"))

save_figure(p, "figure4_temporary_life_expectancy_30_70",
            width_in = 6.5, height_in = 4.2)
message("Wrote figure4_temporary_life_expectancy_30_70.{pdf,png}")
