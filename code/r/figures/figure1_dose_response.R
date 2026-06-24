## Figure 1. Dose-response: HR by MSA frequency, main and 24-month lagged models.
## Lancet-style forest layout: square markers, thin whiskers, navy/red palette.

suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
  library(ggplot2)
  library(scales)
})
source(file.path("code", "r", "figures", "theme_paper.R"))

dat_raw <- read_csv(
  file.path("outputs", "tables", "msa_dose_response_plot_data.csv"),
  show_col_types = FALSE
)

dat <- dat_raw %>%
  filter(model_name %in% c("Model 5", "Model 5 lag24")) %>%
  mutate(
    series = ifelse(model_name == "Model 5", "Main", "24-month lagged"),
    msa_category = ifelse(is.na(msa_category) | msa_category == "", "0", msa_category),
    freq_label = recode(msa_category,
      "0" = "0", "1 day/week" = "1", "2 days/week" = "2",
      "3-4 days/week" = "3-4", "5+ days/week" = "5+"
    ),
    freq_label = factor(freq_label, levels = freq_levels),
    series = factor(series, levels = c("Main", "24-month lagged"))
  ) %>%
  filter(!is.na(freq_label)) %>%
  rename(hr = hazard_ratio, lo = ci_lower, hi = ci_upper)

dodge <- position_dodge(width = 0.42)

p <- ggplot(dat, aes(x = freq_label, y = hr, color = series, shape = series)) +
  geom_hline(yintercept = 1, linetype = "dashed",
             color = "grey45", linewidth = 0.35) +
  geom_errorbar(aes(ymin = lo, ymax = hi), width = 0,
                position = dodge, linewidth = 0.5) +
  geom_point(position = dodge, size = 2.0, fill = "white", stroke = 0.7) +
  scale_color_manual(values = model_palette) +
  scale_shape_manual(values = c(Main = 15, `24-month lagged` = 22)) +
  scale_y_continuous(limits = c(0.80, 1.13),
                     breaks = seq(0.80, 1.10, by = 0.05)) +
  labs(x = "MSA frequency (times per week; reference = 0)",
       y = "Adjusted hazard ratio for all-cause mortality") +
  theme_paper() +
  theme(legend.position = "top",
        legend.direction = "horizontal")

save_figure(p, "figure1_dose_response_hr", width_in = 5.6, height_in = 3.4)
message("Wrote figure1_dose_response_hr.{pdf,png}")
