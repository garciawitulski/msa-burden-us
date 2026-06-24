## Figure 2 (manuscript). Six-panel main results, Lancet-style (3 rows x 2 cols).
## A: forest plot of dose-response HR (sensitivity).
## B: population pyramid of attributable deaths.
## C: cumulative mortality curves -- women (observed vs counterfactual).
## D: cumulative mortality curves -- men (observed vs counterfactual).
## E: Cleveland dot plot of YLL.
## F: lollipop chart of productivity losses.
##
## Note: filename retained as figure1_main_four_panel.{pdf,png} for backward
## compatibility with main_tables_figures.tex.

suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
  library(tidyr)
  library(ggplot2)
  library(patchwork)
  library(scales)
})
source(file.path("code", "r", "figures", "theme_paper.R"))

## ===== Refreshed palette =================================================
fig_palette <- c(
  Female      = "#B5394F",
  Male        = "#2D5878",
  Main        = "#1F1F1F",
  `24-month lagged` = "#8B7E70",
  ref_line    = "#5C5C5C",
  shade_block = "grey92"
)
sex_pal <- fig_palette[c("Female", "Male")]
sens_pal <- fig_palette[c("Main", "24-month lagged")]

figure2_width_in <- 7.8
figure2_height_in <- 10.5

panel_title <- function(tag, title) paste(tag, title, sep = "  ")

age_pos <- tibble(
  age_group = factor(age_levels_5, levels = age_levels_5),
  age_num = seq_along(age_levels_5)
)
sex_offsets <- c(Female = -0.14, Male = 0.14)

theme_lancet_panel <- function(base_size = 7.8) {
  theme_paper(base_size = base_size) +
    theme(
      plot.title = element_text(
        face = "bold", size = base_size + 0.9, color = "black",
        hjust = 0, margin = margin(b = 2)
      ),
      plot.title.position = "plot",
      plot.subtitle = element_text(
        size = base_size - 0.1, color = "grey28", hjust = 0,
        margin = margin(b = 7), lineheight = 1.08
      ),
      axis.title = element_text(size = base_size, color = "black"),
      axis.text = element_text(size = base_size - 0.3, color = "black"),
      panel.grid.major.x = element_line(color = "grey94", linewidth = 0.22),
      panel.grid.major.y = element_blank(),
      plot.margin = margin(8, 12, 8, 7)
    )
}

## ===== Data ==============================================================
hr_dat <- read_csv(
  file.path("outputs", "tables", "msa_dose_response_plot_data.csv"),
  show_col_types = FALSE
) %>%
  filter(model_name %in% c("Model 5", "Model 5 lag24")) %>%
  mutate(
    series = ifelse(model_name == "Model 5", "Main", "24-month lagged"),
    msa_category = ifelse(is.na(msa_category) | msa_category == "",
                          "0", msa_category),
    freq_label = recode(
      msa_category,
      "0" = "0", "1 day/week" = "1", "2 days/week" = "2",
      "3-4 days/week" = "3-4", "5+ days/week" = "5+"
    ),
    freq_label = factor(freq_label, levels = freq_levels),
    series = factor(series, levels = c("Main", "24-month lagged"))
  ) %>%
  filter(!is.na(freq_label)) %>%
  filter(!(series == "24-month lagged" & freq_label == "0")) %>%
  rename(hr = hazard_ratio, lo = ci_lower, hi = ci_upper)

burden <- read_csv(
  file.path("outputs", "tables",
            "msa_burden_contributions_by_age_sex_premature_30_69.csv"),
  show_col_types = FALSE
) %>%
  mutate(
    age_group = factor(age_group, levels = age_levels_5),
    sex = factor(sex, levels = sex_levels)
  )

prod <- read_csv(
  file.path("outputs", "tables",
            "msa_productivity_losses_by_age_sex_premature_30_69_nhis2024.csv"),
  show_col_types = FALSE
) %>%
  filter(
    earnings_measure == "pernp_mean",
    productive_horizon == 65,
    abs(discount_rate - 0.03) < 1e-9
  ) %>%
  mutate(
    age_group = factor(age_group, levels = age_levels_5),
    sex = factor(sex, levels = sex_levels),
    productivity_loss_millions = productivity_loss / 1e6,
    ui_ratio_lo = attributable_deaths_p2_5 / attributable_deaths,
    ui_ratio_hi = attributable_deaths_p97_5 / attributable_deaths,
    productivity_loss_p2_5_millions = productivity_loss_millions * ui_ratio_lo,
    productivity_loss_p97_5_millions = productivity_loss_millions * ui_ratio_hi,
    valuation_in_horizon = age_group != "65-69"
  )

## Survival-curve data for panels C and D
lt <- read_csv(
  file.path("outputs", "tables",
            "msa_life_table_observed_counterfactual_premature_30_69_nhis2024.csv"),
  show_col_types = FALSE
) %>%
  filter(sex %in% c("Female", "Male"),
         scenario %in% c("observed", "counterfactual"))

build_curve <- function(df_subset) {
  df_subset <- df_subset %>% arrange(age_start)
  tibble(
    age = c(df_subset$age_start[1], df_subset$age_end),
    p_death_pct = 100 * (1 - c(df_subset$lx[1], df_subset$lx_next) / 100000)
  )
}

surv_curves <- lt %>%
  group_by(sex, scenario) %>%
  group_modify(~ build_curve(.x)) %>%
  ungroup() %>%
  mutate(
    sex = factor(sex, levels = c("Female", "Male")),
    scenario = factor(scenario, levels = c("observed", "counterfactual"))
  )

surv_wide <- surv_curves %>%
  pivot_wider(names_from = scenario, values_from = p_death_pct)

surv_stats <- surv_wide %>%
  filter(age == 70) %>%
  mutate(
    delta = observed - counterfactual,
    deaths_avert = round(delta * 1000)
  )

## ===== Panel A: forest plot of dose-response HR ==========================
panel_hr <- ggplot(
  hr_dat,
  aes(x = freq_label, y = hr, color = series, shape = series)
) +
  geom_hline(
    yintercept = 1, linetype = "dashed",
    color = fig_palette[["ref_line"]], linewidth = 0.32
  ) +
  geom_errorbar(
    aes(ymin = lo, ymax = hi),
    width = 0,
    position = position_dodge(width = 0.45),
    linewidth = 0.45
  ) +
  geom_point(
    position = position_dodge(width = 0.45),
    size = 2.0, fill = "white", stroke = 0.75
  ) +
  scale_color_manual(values = sens_pal, name = NULL) +
  scale_shape_manual(values = c(Main = 16, `24-month lagged` = 21), name = NULL) +
  scale_x_discrete(limits = freq_levels) +
  scale_y_continuous(
    breaks = seq(0.85, 1.10, by = 0.05),
    labels = label_number(accuracy = 0.01)
  ) +
  guides(
    color = guide_legend(override.aes = list(linewidth = 0.45, size = 2.1)),
    shape = guide_legend()
  ) +
  labs(
    title = panel_title("A", "Dose-response association"),
    subtitle = "Adjusted hazard ratio (95% CI) by MSA frequency",
    x = "MSA frequency (times/week)",
    y = "Hazard ratio for all-cause mortality"
  ) +
  theme_lancet_panel() +
  theme(
    legend.position = c(0.99, 1.02),
    legend.justification = c(1, 1),
    legend.direction = "horizontal",
    legend.background = element_rect(fill = "white", color = NA),
    legend.key.width = unit(0.5, "cm"),
    legend.margin = margin(0, 0, 0, 0),
    panel.grid.major.x = element_blank(),
    panel.grid.major.y = element_line(color = "grey94", linewidth = 0.22)
  )

## ===== Panel B: population pyramid of attributable deaths ================
burden_pyr <- burden %>%
  mutate(
    sign = ifelse(sex == "Female", -1, 1),
    deaths_s   = sign * attributable_deaths,
    deaths_lo  = sign * attributable_deaths_p2_5,
    deaths_hi  = sign * attributable_deaths_p97_5,
    deaths_xmin = pmin(deaths_lo, deaths_hi),
    deaths_xmax = pmax(deaths_lo, deaths_hi)
  )

deaths_x_max <- max(burden$attributable_deaths_p97_5, na.rm = TRUE) * 1.10
deaths_breaks <- pretty(c(0, deaths_x_max), n = 4)
deaths_breaks <- deaths_breaks[deaths_breaks > 0]

panel_deaths <- ggplot(
  burden_pyr,
  aes(x = deaths_s, y = age_group, fill = sex)
) +
  geom_col(width = 0.72, color = "grey15", linewidth = 0.16) +
  geom_errorbar(
    aes(xmin = deaths_xmin, xmax = deaths_xmax),
    orientation = "y", width = 0,
    color = "black", linewidth = 0.34
  ) +
  geom_vline(xintercept = 0, color = "black", linewidth = 0.4) +
  annotate(
    "text",
    x = -deaths_x_max * 0.96, y = 5.4, label = "Female",
    hjust = 0, size = 2.55, fontface = "bold", color = sex_pal[["Female"]]
  ) +
  annotate(
    "text",
    x = deaths_x_max * 0.96, y = 5.4, label = "Male",
    hjust = 1, size = 2.55, fontface = "bold", color = sex_pal[["Male"]]
  ) +
  scale_fill_manual(values = sex_pal, guide = "none") +
  scale_x_continuous(
    limits = c(-deaths_x_max, deaths_x_max),
    breaks = c(-rev(deaths_breaks), 0, deaths_breaks),
    labels = function(x) comma(abs(x)),
    expand = expansion(mult = 0)
  ) +
  scale_y_discrete(limits = age_levels_5) +
  coord_cartesian(clip = "off") +
  labs(
    title = panel_title("B", "Attributable deaths"),
    subtitle = sprintf(
      "Total: %s (95%% UI %s-%s)",
      comma(round(sum(burden$attributable_deaths))),
      comma(round(sum(burden$attributable_deaths_p2_5))),
      comma(round(sum(burden$attributable_deaths_p97_5)))
    ),
    x = "Number of deaths",
    y = "Age group (years)"
  ) +
  theme_lancet_panel() +
  theme(
    panel.grid.major.x = element_line(color = "grey94", linewidth = 0.22),
    panel.grid.major.y = element_blank()
  )

## ===== Panel C: Cleveland dot plot of YLL ================================
panel_yll <- ggplot(
  burden %>%
    left_join(age_pos, by = "age_group") %>%
    mutate(y_pos = age_num + unname(sex_offsets[as.character(sex)])),
  aes(x = yll / 1000, y = y_pos, color = sex)
) +
  geom_segment(
    aes(x = yll_p2_5 / 1000, xend = yll_p97_5 / 1000,
        yend = y_pos),
    linewidth = 0.45
  ) +
  geom_point(
    size = 2.4, stroke = 0
  ) +
  annotate(
    "text", x = max(burden$yll_p97_5 / 1000) * 1.0, y = 5.45,
    label = "Female", hjust = 1,
    size = 2.55, fontface = "bold", color = sex_pal[["Female"]]
  ) +
  annotate(
    "text", x = max(burden$yll_p97_5 / 1000) * 1.0, y = 5.20,
    label = "Male", hjust = 1,
    size = 2.55, fontface = "bold", color = sex_pal[["Male"]]
  ) +
  scale_color_manual(values = sex_pal, guide = "none") +
  scale_x_continuous(
    limits = c(0, max(burden$yll_p97_5 / 1000) * 1.06),
    labels = label_comma(),
    expand = expansion(mult = c(0, 0.02))
  ) +
  scale_y_continuous(
    breaks = seq_along(age_levels_5),
    labels = age_levels_5,
    limits = c(0.55, 5.65),
    expand = expansion(mult = 0)
  ) +
  labs(
    title = panel_title("E", "Years of life lost"),
    subtitle = sprintf(
      "Total: %s thousand (95%% UI %s-%s)",
      comma(round(sum(burden$yll) / 1000)),
      comma(round(sum(burden$yll_p2_5) / 1000)),
      comma(round(sum(burden$yll_p97_5) / 1000))
    ),
    x = "YLL (thousands)",
    y = "Age group (years)"
  ) +
  theme_lancet_panel() +
  theme(
    panel.grid.major.x = element_line(color = "grey94", linewidth = 0.22),
    panel.grid.major.y = element_line(color = "grey96", linewidth = 0.22)
  )

## ===== Panel D: lollipop chart of productivity losses ====================
prod_lolli <- prod %>%
  left_join(age_pos, by = "age_group") %>%
  mutate(
    show_alpha = ifelse(valuation_in_horizon, 1, 0.22),
    x_pos = age_num + unname(sex_offsets[as.character(sex)])
  )

prod_y_max <- max(prod$productivity_loss_p97_5_millions, na.rm = TRUE) * 1.08

panel_prod <- ggplot(
  prod_lolli,
  aes(x = x_pos, y = productivity_loss_millions,
      color = sex, alpha = show_alpha)
) +
  ## Shaded "beyond horizon" band for 65-69
  annotate(
    "rect", xmin = 4.5, xmax = 5.5, ymin = 0, ymax = prod_y_max,
    fill = fig_palette[["shade_block"]], alpha = 0.55
  ) +
  geom_segment(
    aes(xend = x_pos, y = 0, yend = productivity_loss_millions),
    linewidth = 0.55
  ) +
  geom_errorbar(
    aes(ymin = productivity_loss_p2_5_millions,
        ymax = productivity_loss_p97_5_millions),
    width = 0, color = "black", linewidth = 0.30,
    show.legend = FALSE
  ) +
  geom_point(
    size = 2.4, stroke = 0
  ) +
  annotate(
    "text", x = 5, y = prod_y_max * 0.50,
    label = "Not valued\nbeyond age 65",
    size = 2.05, color = "grey25", fontface = "italic", lineheight = 0.95
  ) +
  scale_color_manual(values = sex_pal, guide = "none") +
  scale_alpha_identity(guide = "none") +
  scale_x_continuous(
    breaks = seq_along(age_levels_5),
    labels = age_levels_5,
    limits = c(0.55, 5.55),
    expand = expansion(mult = 0)
  ) +
  scale_y_continuous(
    limits = c(0, prod_y_max),
    breaks = pretty(c(0, prod_y_max), n = 5),
    labels = label_comma(),
    expand = expansion(mult = c(0, 0.02))
  ) +
  labs(
    title = panel_title("F", "Productivity losses"),
    subtitle = sprintf(
      "Total ages 30-64: US$%.1f billion (3%% discount; through age 65)",
      sum(prod$productivity_loss_millions[prod$valuation_in_horizon]) / 1000
    ),
    x = "Age group (years)",
    y = "US$ millions"
  ) +
  theme_lancet_panel() +
  theme(
    panel.grid.major.y = element_line(color = "grey94", linewidth = 0.22),
    panel.grid.major.x = element_blank()
  )

## ===== Panels C and D: cumulative-mortality curves by sex ================
make_surv_panel <- function(sex_var, panel_letter, panel_title_text, color) {
  data_w <- surv_wide %>% filter(sex == sex_var)
  data_l <- surv_curves %>% filter(sex == sex_var)
  stat <- surv_stats %>% filter(sex == sex_var)

  callout_label <- sprintf(
    "At age 70:\nObserved: %.2f%%\nCounterfactual: %.2f%%\nGap = %.2f pp\n%s averted/100k",
    stat$observed, stat$counterfactual, stat$delta,
    format(stat$deaths_avert, big.mark = ",")
  )

  ggplot(data_l, aes(x = age, y = p_death_pct)) +
    geom_ribbon(
      data = data_w,
      aes(x = age, ymin = counterfactual, ymax = observed),
      inherit.aes = FALSE, fill = color, alpha = 0.16
    ) +
    geom_line(aes(linetype = scenario), color = color, linewidth = 0.7) +
    geom_point(
      aes(shape = scenario, fill = scenario),
      color = color, size = 1.85, stroke = 0.7
    ) +
    annotate(
      "label", x = 30.4, y = 28.5,
      label = callout_label,
      size = 1.95, hjust = 0, vjust = 1,
      color = "grey15", fill = "white",
      label.r = unit(0.12, "lines"),
      lineheight = 1.0
    ) +
    scale_linetype_manual(
      values = c(observed = "solid", counterfactual = "longdash"),
      labels = c(observed = "Observed", counterfactual = "Counterfactual"),
      name = NULL
    ) +
    scale_shape_manual(
      values = c(observed = 16, counterfactual = 21),
      labels = c(observed = "Observed", counterfactual = "Counterfactual"),
      name = NULL
    ) +
    scale_fill_manual(
      values = c(observed = color, counterfactual = "white"),
      labels = c(observed = "Observed", counterfactual = "Counterfactual"),
      name = NULL
    ) +
    scale_x_continuous(
      breaks = c(30, 35, 45, 55, 65, 70),
      limits = c(29, 71),
      expand = expansion(mult = 0.01)
    ) +
    scale_y_continuous(
      breaks = seq(0, 30, by = 5),
      expand = expansion(add = c(0, 0))
    ) +
    coord_cartesian(ylim = c(0, 30.8), clip = "off") +
    labs(
      title = panel_title(
        panel_letter,
        sprintf("Cumulative probability of death since age 30 (%%) - %s",
                panel_title_text)
      ),
      subtitle = NULL,
      x = "Age (years)",
      y = "Cumulative probability of death (%)"
    ) +
    theme_lancet_panel() +
    theme(
      legend.position = c(0.99, 0.02),
      legend.justification = c(1, 0),
      legend.background = element_rect(fill = "white", color = NA),
      legend.key.height = unit(0.32, "cm"),
      legend.key.width = unit(0.55, "cm"),
      panel.grid.major.x = element_line(color = "grey94", linewidth = 0.22),
      panel.grid.major.y = element_line(color = "grey94", linewidth = 0.22)
    )
}

panel_surv_F <- make_surv_panel("Female", "C", "Women", sex_pal[["Female"]])
panel_surv_M <- make_surv_panel("Male",   "D", "Men",   sex_pal[["Male"]])

## ===== Compose ===========================================================
p <- (panel_hr | panel_deaths) /
     (panel_surv_F | panel_surv_M) /
     (panel_yll | panel_prod) +
  plot_layout(heights = c(1, 1, 1), widths = c(1, 1)) +
  plot_annotation(
    theme = theme(plot.margin = margin(4, 5, 4, 5))
  )

save_figure(
  p, "figure1_main_four_panel",
  width_in = figure2_width_in, height_in = figure2_height_in
)
message("Wrote figure1_main_four_panel.{pdf,png}")
