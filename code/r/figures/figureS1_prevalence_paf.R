## Supplementary Figure S1. Prevalence (A) and PAF (B) of insufficient MSA
## by age and sex. Demoted from main Figure 2 to supplementary per AJPM 4-float limit.

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

hr_inputs <- read_csv(
  file.path("outputs", "tables", "hr_inputs_for_burden.csv"),
  show_col_types = FALSE
)
main_hr <- hr_inputs %>% filter(scenario == "main_hr_target_30_69")
HR_LO <- main_hr$ci_lower
HR_HI <- main_hr$ci_upper
dat <- t3 %>%
  mutate(age_group = factor(age_group, levels = age_levels_5),
         sex = factor(sex, levels = sex_levels),
         p = insufficient_MSA_percent / 100,
         paf_lo = (p * (HR_LO - 1)) / (1 + p * (HR_LO - 1)) * 100,
         paf_hi = (p * (HR_HI - 1)) / (1 + p * (HR_HI - 1)) * 100)

dodge <- position_dodge(width = 0.62)

p_prev <- ggplot(dat, aes(x = age_group, y = insufficient_MSA_percent, fill = sex)) +
  geom_col(position = dodge, width = 0.55, color = "black", linewidth = 0.25) +
  scale_fill_manual(values = sex_palette) +
  scale_y_continuous(limits = c(0, 90), breaks = seq(0, 80, 20),
                     labels = function(x) paste0(x, "%"),
                     expand = expansion(mult = c(0, 0.02))) +
  labs(x = NULL, y = "Insufficient MSA (% of adults)", tag = "A") +
  theme_paper() +
  theme(legend.position = "top", legend.direction = "horizontal")

p_paf <- ggplot(dat, aes(x = age_group, y = PAF_percent, color = sex)) +
  geom_errorbar(aes(ymin = paf_lo, ymax = paf_hi), width = 0,
                position = dodge, linewidth = 0.5) +
  geom_point(position = dodge, size = 1.9) +
  scale_color_manual(values = sex_palette, guide = "none") +
  scale_y_continuous(limits = c(0, 8.2), breaks = seq(0, 8, 2),
                     labels = function(x) paste0(x, "%"),
                     expand = expansion(mult = c(0, 0.02))) +
  labs(x = "Age group (years)", y = "Population attributable fraction",
       tag = "B") +
  theme_paper()

p <- p_prev / p_paf + plot_layout(heights = c(1, 1))

save_figure(p, "figureS1_prevalence_paf", width_in = 5.6, height_in = 5.4)
message("Wrote figureS1_prevalence_paf.{pdf,png}")
