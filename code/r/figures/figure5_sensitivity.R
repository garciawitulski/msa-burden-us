## Figure 5. Sensitivity panel: PAF and attributable deaths under three scenarios.

suppressPackageStartupMessages({
  library(dplyr)
  library(ggplot2)
  library(patchwork)
  library(scales)
})
source(file.path("code", "r", "figures", "theme_paper.R"))

scen <- tibble::tribble(
  ~scenario,           ~paf_pct, ~deaths,  ~deaths_lo, ~deaths_hi,
  "Main HR (age-sex)", 4.61,     44745,    23150,      65742,
  "24-month lagged HR", NA_real_, 41801,    19257,      64030,
  "Overall PAF",       4.61,     43168,    NA_real_,   NA_real_
) %>%
  mutate(scenario = factor(scenario,
                           levels = c("Main HR (age-sex)", "24-month lagged HR", "Overall PAF")))

p_paf <- scen %>% filter(!is.na(paf_pct)) %>%
  ggplot(aes(x = scenario, y = paf_pct, color = scenario)) +
  geom_segment(aes(xend = scenario, y = 0, yend = paf_pct), linewidth = 0.4) +
  geom_point(size = 3) +
  geom_text(aes(label = sprintf("%.2f%%", paf_pct)),
            vjust = -1.0, size = 2.9, color = "grey15") +
  scale_color_manual(values = scenario_palette, guide = "none") +
  scale_y_continuous(limits = c(0, 6.0), breaks = seq(0, 6, 1),
                     labels = function(x) paste0(x, "%")) +
  labs(x = NULL, y = "Population attributable fraction",
       subtitle = "(a) Overall PAF") +
  theme_paper() +
  theme(axis.text.x = element_text(angle = 12, hjust = 0.7))

p_d <- ggplot(scen, aes(x = scenario, y = deaths, color = scenario)) +
  geom_errorbar(aes(ymin = deaths_lo, ymax = deaths_hi), width = 0.18, linewidth = 0.5) +
  geom_point(size = 3) +
  geom_text(aes(label = label_comma()(deaths)), vjust = -1.0,
            size = 2.9, color = "grey15") +
  scale_color_manual(values = scenario_palette, guide = "none") +
  scale_y_continuous(limits = c(0, 70000), labels = label_comma()) +
  labs(x = NULL, y = "Potentially attributable deaths",
       subtitle = "(b) Attributable premature deaths") +
  theme_paper() +
  theme(axis.text.x = element_text(angle = 12, hjust = 0.7))

p <- p_paf + p_d + plot_layout(widths = c(1, 1))

save_figure(p, "figure5_sensitivity", width_in = 7.0, height_in = 3.8)
message("Wrote figure5_sensitivity.{pdf,png}")
