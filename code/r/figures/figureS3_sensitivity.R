## Supplementary Figure S3. Sensitivity of overall PAF (A) and attributable
## deaths (B) under main target HR, lagged HR, adult-refined HR comparison,
## and overall-PAF reconciliation.

suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
  library(ggplot2)
  library(patchwork)
  library(scales)
})
source(file.path("code", "r", "figures", "theme_paper.R"))

summary <- read_csv(
  file.path("outputs", "tables",
            "msa_burden_summary_premature_30_69_nhis2024.csv"),
  show_col_types = FALSE
)
recon <- read_csv(
  file.path("outputs", "tables", "manuscript",
            "supplementary_table_s1_reconciliation.csv"),
  show_col_types = FALSE
)

as_num <- function(x) {
  if (is.numeric(x)) return(as.numeric(x))
  parse_number(as.character(x))
}

main <- summary %>% filter(rr_scenario == "main_hr_target_30_69")
lag24 <- summary %>% filter(rr_scenario == "lag24_hr_target_30_69")
adult <- summary %>% filter(rr_scenario == "main_hr_adult_refined")
total_deaths <- main$deaths_allcause[1]

scen <- bind_rows(
  tibble::tibble(
    scenario = "Age-sex PAFs (main target HR)",
    paf_pct = recon$implied_death_weighted_PAF_percent[1],
    deaths = main$attributable_deaths[1],
    deaths_lo = main$attributable_deaths_p2_5[1],
    deaths_hi = main$attributable_deaths_p97_5[1]
  ),
  tibble::tibble(
    scenario = "24-month lagged target HR",
    paf_pct = lag24$attributable_deaths[1] / total_deaths * 100,
    deaths = lag24$attributable_deaths[1],
    deaths_lo = lag24$attributable_deaths_p2_5[1],
    deaths_hi = lag24$attributable_deaths_p97_5[1]
  ),
  tibble::tibble(
    scenario = "Adult refined HR comparison",
    paf_pct = adult$attributable_deaths[1] / total_deaths * 100,
    deaths = adult$attributable_deaths[1],
    deaths_lo = adult$attributable_deaths_p2_5[1],
    deaths_hi = adult$attributable_deaths_p97_5[1]
  ),
  tibble::tibble(
    scenario = "Overall PAF applied to deaths",
    paf_pct = as_num(recon$overall_PAF_percent[1]),
    deaths = as_num(recon$deaths_using_overall_PAF[1]),
    deaths_lo = NA_real_,
    deaths_hi = NA_real_
  )
) %>%
  mutate(scenario = factor(scenario,
    levels = rev(c("Age-sex PAFs (main target HR)",
                   "24-month lagged target HR",
                   "Adult refined HR comparison",
                   "Overall PAF applied to deaths"))))

p_paf <- scen %>% filter(!is.na(paf_pct)) %>%
  ggplot(aes(y = scenario, x = paf_pct)) +
  geom_col(width = 0.45, fill = unname(lancet_palette["navy"]),
           color = "black", linewidth = 0.25) +
  geom_text(aes(label = sprintf("%.2f%%", paf_pct)), hjust = -0.2,
            size = 2.7, color = "black") +
  scale_x_continuous(limits = c(0, 5.6), breaks = seq(0, 5, 1),
                     labels = function(x) paste0(x, "%"),
                     expand = c(0, 0)) +
  labs(x = "Population attributable fraction", y = NULL, tag = "A") +
  theme_paper() +
  theme(axis.line.y = element_blank(), axis.ticks.y = element_blank())

p_d <- ggplot(scen, aes(y = scenario, x = deaths)) +
  geom_vline(xintercept = 0, linetype = "dashed", color = "grey55",
             linewidth = 0.35) +
  geom_errorbarh(aes(xmin = deaths_lo, xmax = deaths_hi), height = 0,
                 color = unname(lancet_palette["navy"]), linewidth = 0.5,
                 na.rm = TRUE) +
  geom_point(size = 2.0, color = unname(lancet_palette["navy"]),
             fill = "white", shape = 22, stroke = 0.7) +
  geom_text(aes(label = label_comma()(round(deaths))), vjust = -1.0, hjust = 0.5,
            size = 2.7, color = "black") +
  scale_x_continuous(limits = c(-10000, 85000), breaks = seq(0, 80000, 20000),
                     labels = label_comma(), expand = c(0, 0)) +
  labs(x = "Potentially attributable deaths", y = NULL, tag = "B") +
  theme_paper() +
  theme(axis.line.y = element_blank(), axis.ticks.y = element_blank())

p <- p_paf / p_d + plot_layout(heights = c(1, 1.1))

save_figure(p, "figureS3_sensitivity", width_in = 5.8, height_in = 4.6)
message("Wrote figureS3_sensitivity.{pdf,png}")
