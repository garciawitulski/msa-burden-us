## Supplementary Figure S2. Life expectancy gains from age 30 to 70,
## total and by sex, with 95% UI from HR uncertainty.
## Forest-style display of the difference (gain) only.

suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
  library(ggplot2)
})
source(file.path("code", "r", "figures", "theme_paper.R"))

mc <- read_csv(
  file.path("outputs", "tables",
            "msa_life_expectancy_gain_montecarlo_premature_30_69_nhis2024.csv"),
  show_col_types = FALSE
)

tle <- read_csv(
  file.path("outputs", "tables",
            "msa_life_expectancy_gain_premature_30_69_nhis2024.csv"),
  show_col_types = FALSE
) %>%
  select(sex, point = gain_temporary_life_expectancy_30_70)

dat <- mc %>%
  select(sex,
         lo = gain_temporary_life_expectancy_30_70_p2_5,
         hi = gain_temporary_life_expectancy_30_70_p97_5) %>%
  left_join(tle, by = "sex") %>%
  mutate(lo = pmax(lo, 0)) %>%
  mutate(label_grp = case_when(sex == "All" ~ "All adults", TRUE ~ sex),
         label_grp = factor(label_grp,
                            levels = rev(c("All adults", "Female", "Male")))) %>%
  arrange(label_grp)

dat_lab <- dat %>%
  mutate(text = sprintf("%.3f (%.3f to %.3f)", point, lo, hi))

p <- ggplot(dat, aes(y = label_grp, x = point)) +
  geom_vline(xintercept = 0, linetype = "dashed", color = "grey50",
             linewidth = 0.35) +
  geom_errorbarh(aes(xmin = lo, xmax = hi), height = 0,
                 color = unname(lancet_palette["navy"]), linewidth = 0.6) +
  geom_point(size = 2.2, color = unname(lancet_palette["navy"]),
             fill = "white", shape = 22, stroke = 0.7) +
  geom_text(data = dat_lab,
            aes(x = 0.30, label = text),
            hjust = 0, size = 2.7, color = "black", family = "sans") +
  scale_x_continuous(limits = c(-0.02, 0.55),
                     breaks = c(0, 0.05, 0.1, 0.15, 0.2),
                     expand = c(0, 0)) +
  labs(x = "Life expectancy gain, ages 30 to 70 (years)", y = NULL) +
  theme_paper() +
  theme(panel.grid.major.y = element_blank(),
        axis.line.y = element_blank(),
        axis.ticks.y = element_blank())

save_figure(p, "figureS2_life_expectancy_gain", width_in = 5.6, height_in = 2.6)
message("Wrote figureS2_life_expectancy_gain.{pdf,png}")
