## Figure 3. Burden cascade: attributable deaths, YLL, and productivity losses
## by age group and sex (3-panel small multiples).

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
  mutate(
    age_group = factor(age_group, levels = age_levels_5),
    sex = factor(sex, levels = sex_levels)
  )

prod_raw <- read_csv(
  file.path("outputs", "tables",
            "msa_productivity_losses_by_age_sex_premature_30_69_nhis2024.csv"),
  show_col_types = FALSE
)

prod <- prod_raw %>%
  filter(earnings_measure == "pernp_mean",
         productive_horizon == 65,
         abs(discount_rate - 0.03) < 1e-9) %>%
  mutate(
    age_group = factor(age_group, levels = age_levels_5),
    sex = factor(sex, levels = sex_levels),
    productivity_loss_millions = productivity_loss / 1e6
  )

dodge <- position_dodge(width = 0.65)

p_deaths <- ggplot(burden, aes(x = age_group, y = attributable_deaths,
                                fill = sex, color = sex)) +
  geom_col(position = dodge, width = 0.6, alpha = 0.85) +
  geom_errorbar(aes(ymin = attributable_deaths_p2_5,
                    ymax = attributable_deaths_p97_5),
                position = dodge, width = 0.18, color = "grey25", linewidth = 0.4) +
  scale_fill_manual(values = sex_palette, name = NULL) +
  scale_color_manual(values = sex_palette, guide = "none") +
  scale_y_continuous(limits = c(0, 17000), labels = label_comma()) +
  labs(x = NULL, y = "Attributable deaths",
       subtitle = "(a) Potentially attributable premature deaths") +
  theme_paper() +
  theme(legend.position = "top")

p_yll <- ggplot(burden, aes(x = age_group, y = yll / 1000,
                             fill = sex, color = sex)) +
  geom_col(position = dodge, width = 0.6, alpha = 0.85) +
  geom_errorbar(aes(ymin = yll_p2_5 / 1000, ymax = yll_p97_5 / 1000),
                position = dodge, width = 0.18, color = "grey25", linewidth = 0.4) +
  scale_fill_manual(values = sex_palette, guide = "none") +
  scale_color_manual(values = sex_palette, guide = "none") +
  scale_y_continuous(limits = c(0, 360), labels = label_comma()) +
  labs(x = NULL, y = "YLL, thousands",
       subtitle = "(b) Years of life lost") +
  theme_paper()

zero_label <- prod %>% filter(age_group == "65-69")

p_prod <- ggplot(prod, aes(x = age_group, y = productivity_loss_millions,
                            fill = sex, color = sex)) +
  geom_col(position = dodge, width = 0.6, alpha = 0.85) +
  geom_text(data = zero_label,
            aes(x = age_group, y = 200, label = "Beyond age-65\nvaluation horizon"),
            inherit.aes = FALSE, size = 2.5, color = "grey35",
            fontface = "italic", lineheight = 0.9) +
  scale_fill_manual(values = sex_palette, guide = "none") +
  scale_color_manual(values = sex_palette, guide = "none") +
  scale_y_continuous(limits = c(0, 6800), labels = label_comma()) +
  labs(x = "Age group, years", y = "Productivity losses, US$ millions",
       subtitle = "(c) Indirect productivity losses") +
  theme_paper()

p <- p_deaths / p_yll / p_prod + plot_layout(heights = c(1, 1, 1))

save_figure(p, "figure3_burden_cascade", width_in = 6.8, height_in = 8.2)
message("Wrote figure3_burden_cascade.{pdf,png}")
