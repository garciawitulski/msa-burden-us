## Figure 2. Two-panel: prevalence (top) and PAF with HR-CI bounds (bottom),
## by age group and sex.

suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
  library(ggplot2)
  library(patchwork)
  library(scales)
})
source(file.path("code", "r", "figures", "theme_paper.R"))

t3 <- read_csv(
  file.path("outputs", "tables", "manuscript", "table3_nhis2024_prevalence_paf.csv"),
  show_col_types = FALSE
)

HR_LO <- 1.036
HR_HI <- 1.108

dat <- t3 %>%
  mutate(
    age_group = factor(age_group, levels = age_levels_5),
    sex = factor(sex, levels = sex_levels),
    p = insufficient_MSA_percent / 100,
    paf_lo = (p * (HR_LO - 1)) / (1 + p * (HR_LO - 1)) * 100,
    paf_hi = (p * (HR_HI - 1)) / (1 + p * (HR_HI - 1)) * 100
  )

dodge <- position_dodge(width = 0.6)

p_prev <- ggplot(dat, aes(x = age_group, y = insufficient_MSA_percent,
                          fill = sex, color = sex)) +
  geom_col(position = dodge, width = 0.55, alpha = 0.85) +
  geom_text(aes(label = sprintf("%.1f", insufficient_MSA_percent)),
            position = dodge, vjust = -0.4, size = 2.8, color = "grey15") +
  scale_fill_manual(values = sex_palette, name = NULL) +
  scale_color_manual(values = sex_palette, name = NULL, guide = "none") +
  scale_y_continuous(limits = c(0, 90), breaks = seq(0, 80, 20),
                     labels = function(x) paste0(x, "%")) +
  labs(x = NULL, y = "Insufficient MSA (% of adults)",
       subtitle = "(a) Weighted prevalence, NHIS 2024") +
  theme_paper() +
  theme(legend.position = "top")

p_paf <- ggplot(dat, aes(x = age_group, y = PAF_percent, color = sex)) +
  geom_errorbar(aes(ymin = paf_lo, ymax = paf_hi), width = 0.18,
                position = dodge, linewidth = 0.5) +
  geom_point(position = dodge, size = 2.6) +
  scale_color_manual(values = sex_palette, name = NULL) +
  scale_y_continuous(limits = c(0, 8), breaks = seq(0, 8, 2),
                     labels = function(x) paste0(x, "%")) +
  labs(x = "Age group, years", y = "Population attributable fraction",
       subtitle = "(b) PAF (whiskers from HR 95% CI bounds)") +
  theme_paper() +
  theme(legend.position = "none")

p <- p_prev / p_paf + plot_layout(heights = c(1, 1))

save_figure(p, "figure2_prevalence_paf_age_sex", width_in = 6.5, height_in = 6.2)
message("Wrote figure2_prevalence_paf_age_sex.{pdf,png}")
