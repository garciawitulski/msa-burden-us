## Figure 2. Burden cascade: attributable deaths, YLL, and productivity losses
## by age and sex (3-panel small multiples, vertical stack).
## Lancet-style: bold A/B/C tags, navy/red palette, thin axis line, value labels.

suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
  library(ggplot2)
  library(patchwork)
  library(scales)
})
source(file.path("code", "r", "figures", "theme_paper.R"))

burden <- read_csv(
  file.path("outputs", "tables",
            "msa_burden_contributions_by_age_sex_premature_30_69.csv"),
  show_col_types = FALSE
) %>%
  mutate(age_group = factor(age_group, levels = age_levels_5),
         sex = factor(sex, levels = sex_levels))

prod_raw <- read_csv(
  file.path("outputs", "tables",
            "msa_productivity_losses_by_age_sex_premature_30_69_nhis2024.csv"),
  show_col_types = FALSE
)
prod <- prod_raw %>%
  filter(earnings_measure == "pernp_mean",
         productive_horizon == 65,
         abs(discount_rate - 0.03) < 1e-9) %>%
  mutate(age_group = factor(age_group, levels = age_levels_5),
         sex = factor(sex, levels = sex_levels),
         productivity_loss_millions = productivity_loss / 1e6)

dodge <- position_dodge(width = 0.62)
bar_w <- 0.55

panel_deaths <- ggplot(burden, aes(x = age_group, y = attributable_deaths,
                                   fill = sex)) +
  geom_col(position = dodge, width = bar_w,
           color = "black", linewidth = 0.25) +
  geom_errorbar(aes(ymin = attributable_deaths_p2_5,
                    ymax = attributable_deaths_p97_5),
                position = dodge, width = 0, color = "black", linewidth = 0.4) +
  scale_fill_manual(values = sex_palette) +
  scale_y_continuous(limits = c(0, 17000), breaks = seq(0, 16000, 4000),
                     labels = label_comma(), expand = expansion(mult = c(0, 0.02))) +
  labs(x = NULL, y = "Attributable deaths", tag = "A") +
  theme_paper() +
  theme(legend.position = "top", legend.direction = "horizontal")

panel_yll <- ggplot(burden, aes(x = age_group, y = yll / 1000, fill = sex)) +
  geom_col(position = dodge, width = bar_w,
           color = "black", linewidth = 0.25) +
  geom_errorbar(aes(ymin = yll_p2_5 / 1000, ymax = yll_p97_5 / 1000),
                position = dodge, width = 0, color = "black", linewidth = 0.4) +
  scale_fill_manual(values = sex_palette, guide = "none") +
  scale_y_continuous(limits = c(0, 360), breaks = seq(0, 350, 100),
                     labels = label_comma(), expand = expansion(mult = c(0, 0.02))) +
  labs(x = NULL, y = "Years of life lost (thousands)", tag = "B") +
  theme_paper()

panel_prod <- ggplot(prod, aes(x = age_group, y = productivity_loss_millions,
                                fill = sex)) +
  geom_col(position = dodge, width = bar_w,
           color = "black", linewidth = 0.25) +
  scale_fill_manual(values = sex_palette, guide = "none") +
  scale_y_continuous(limits = c(0, 5800), breaks = seq(0, 5500, 1500),
                     labels = label_comma(), expand = expansion(mult = c(0, 0.02))) +
  annotate("text", x = 5, y = 600,
           label = "Beyond age-65\nvaluation horizon",
           size = 2.4, color = "grey25", fontface = "italic", lineheight = 0.9) +
  labs(x = "Age group (years)", y = "Productivity losses (US$ millions)",
       tag = "C") +
  theme_paper()

p <- panel_deaths / panel_yll / panel_prod + plot_layout(heights = c(1, 1, 1))

save_figure(p, "figure2_burden_cascade", width_in = 5.6, height_in = 7.6)
message("Wrote figure2_burden_cascade.{pdf,png}")
