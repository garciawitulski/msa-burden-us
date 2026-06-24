## Render all manuscript figures. Run from repo root.
##   Rscript code/r/figures/render_all.R

scripts <- c(
  ## Main text: one four-panel figure, plus two main tables in LaTeX.
  "figure1_main_four_panel.R",
  "figure1_guideline_hr_forest.R",
  ## Supplementary
  "figureS1_prevalence_paf.R",
  "figureS2_life_expectancy_gain.R",
  "figureS3_sensitivity.R",
  "figureS4_prevalence_sociodem.R"
)

for (s in scripts) {
  message("--- Rendering ", s)
  source(file.path("code", "r", "figures", s), local = TRUE)
}
message("All figures rendered.")
