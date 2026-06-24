## Figure: guideline-contrast HR forest plot.
## Shows the primary insufficient-versus-sufficient MSA contrast across refined
## Cox model specifications.

suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
  library(ggplot2)
  library(scales)
})
source(file.path("code", "r", "figures", "theme_paper.R"))

dat <- read_csv(
  file.path("outputs", "tables", "refined_cox_msa_allcause.csv"),
  show_col_types = FALSE
) %>%
  filter(exposure_spec == "Guideline",
         term == "1.insufficient_msa") %>%
  mutate(
    model_group = if_else(dataset == "lag24", "24-month lagged", "Main"),
    model_label_clean = case_when(
      model_label == "Model A age time" ~ "Age time scale",
      model_label == "Model B strata sex" ~ "+ sex strata",
      model_label == "Model C strata year" ~ "+ survey-year strata",
      model_label == "Model D strata sex year" ~ "Primary: + sex/year strata",
      model_label == "Model E lag24 age time" ~ "Lag-24: age time scale",
      model_label == "Model E lag24 strata sex year" ~ "Lag-24: + sex/year strata",
      TRUE ~ model_label
    ),
    model_label_clean = factor(
      model_label_clean,
      levels = rev(c(
        "Age time scale",
        "+ sex strata",
        "+ survey-year strata",
        "Primary: + sex/year strata",
        "Lag-24: age time scale",
        "Lag-24: + sex/year strata"
      ))
    ),
    model_group = factor(model_group, levels = c("Main", "24-month lagged")),
    is_primary = model_label == "Model D strata sex year",
    hr_text = sprintf("%.3f (%.3f-%.3f)", hazard_ratio, ci_lower, ci_upper)
  ) %>%
  filter(!is.na(model_label_clean))

p <- ggplot(dat, aes(y = model_label_clean, x = hazard_ratio,
                     xmin = ci_lower, xmax = ci_upper, color = model_group)) +
  geom_vline(xintercept = 1, linetype = "dashed",
             color = "grey45", linewidth = 0.35) +
  geom_errorbar(width = 0, linewidth = 0.55, orientation = "y") +
  geom_point(aes(shape = is_primary), size = 2.3, fill = "white",
             stroke = 0.85) +
  geom_text(aes(label = hr_text), x = 1.123, hjust = 0,
            color = "black", size = 2.45, show.legend = FALSE) +
  scale_color_manual(values = model_palette) +
  scale_shape_manual(values = c(`FALSE` = 16, `TRUE` = 15),
                     guide = "none") +
  scale_x_continuous(
    limits = c(1.00, 1.155),
    breaks = seq(1.00, 1.15, by = 0.03),
    labels = label_number(accuracy = 0.01),
    expand = expansion(mult = c(0.00, 0.01))
  ) +
  labs(
    x = "Adjusted hazard ratio for all-cause mortality",
    y = NULL,
    caption = "Insufficient MSA (<2 times/week) versus sufficient MSA (>=2 times/week); HR (95% CI)."
  ) +
  theme_paper() +
  theme(
    legend.position = "top",
    legend.direction = "horizontal",
    panel.grid.major.y = element_blank(),
    panel.grid.major.x = element_line(color = "grey92", linewidth = 0.25),
    axis.text.y = element_text(hjust = 0),
    plot.margin = margin(8, 54, 6, 6)
  )

save_figure(p, "figure1_guideline_hr_forest", width_in = 6.4, height_in = 3.6)
message("Wrote figure1_guideline_hr_forest.{pdf,png}")
