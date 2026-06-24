## Figure: guideline-contrast HR for insufficient versus sufficient MSA.
## Uses the same visual language as the dose-response HR panel, but shows the
## primary binary contrast used in the burden calculations.

suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
  library(ggplot2)
  library(scales)
})
source(file.path("code", "r", "figures", "theme_paper.R"))

hr_dat <- read_csv(
  file.path("outputs", "tables", "hr_inputs_for_burden.csv"),
  show_col_types = FALSE
) %>%
  filter(scenario %in% c("main_hr_adult_refined",
                         "lag24_hr_adult_refined")) %>%
  mutate(
    series = recode(
      scenario,
      main_hr_adult_refined = "Main",
      lag24_hr_adult_refined = "24-month lagged"
    ),
    series = factor(series, levels = c("Main", "24-month lagged")),
    guideline_status = factor(
      "Insufficient\n(<2 times/week)",
      levels = c("Sufficient\n(>=2 times/week;\nreference)",
                 "Insufficient\n(<2 times/week)")
    ),
    hr_label = sprintf("%.3f", hr)
  )

ref_dat <- tibble(
  guideline_status = factor(
    "Sufficient\n(>=2 times/week;\nreference)",
    levels = levels(hr_dat$guideline_status)
  ),
  hr = 1
)

dodge <- position_dodge(width = 0.38)

p <- ggplot(hr_dat, aes(x = guideline_status, y = hr,
                        color = series, shape = series)) +
  geom_hline(yintercept = 1, linetype = "dashed",
             color = "grey45", linewidth = 0.35) +
  geom_point(data = ref_dat, aes(x = guideline_status, y = hr),
             inherit.aes = FALSE, shape = 21, fill = "white",
             color = "grey35", stroke = 0.75, size = 2.1) +
  geom_errorbar(aes(ymin = ci_lower, ymax = ci_upper),
                width = 0, position = dodge, linewidth = 0.5) +
  geom_point(position = dodge, size = 2.1, fill = "white", stroke = 0.75) +
  geom_text(aes(label = hr_label), position = dodge, vjust = -1.15,
            size = 2.5, show.legend = FALSE) +
  scale_color_manual(values = model_palette) +
  scale_shape_manual(values = c(Main = 15, `24-month lagged` = 22)) +
  scale_y_continuous(
    limits = c(0.99, 1.13),
    breaks = seq(1.00, 1.12, by = 0.03),
    labels = label_number(accuracy = 0.01)
  ) +
  labs(
    x = "MSA guideline status",
    y = "Adjusted hazard ratio for all-cause mortality",
    caption = "Reference group is sufficient MSA, operationalized as >=2 times/week."
  ) +
  theme_paper() +
  theme(
    legend.position = "top",
    legend.direction = "horizontal",
    axis.text.x = element_text(lineheight = 0.95)
  )

save_figure(p, "figure1_guideline_contrast_hr", width_in = 5.6, height_in = 3.4)
message("Wrote figure1_guideline_contrast_hr.{pdf,png}")
