## Render separate PCD figure files. Run from the repository root.
##   Rscript code/r/figures/render_pcd_submission_figures.R

source(file.path("code", "r", "figures", "theme_paper.R"))

records <- list()

## Figure 1 is the analytic-framework TikZ figure used in the manuscript.
records[["Figure_1"]] <- export_pcd_existing_vector_figure(
  source_pdf = file.path(
    "manuscript_latex", "figures", "fig_analytic_framework_tikz.pdf"
  ),
  filename_base = "Figure_1"
)

## Figure 2 is the final R/ggplot manuscript figure.
source(file.path("code", "r", "figures", "figure1_main_four_panel.R"),
       local = FALSE)
records[["Figure_2"]] <- save_pcd_figure(
  plot = p,
  filename_base = "Figure_2",
  width_in = figure2_width_in,
  height_in = figure2_height_in
)

manifest_path <- write_pcd_manifest(records)

message("Wrote PCD figure manifest: ", manifest_path)
message("PCD figure files are in: ", pcd_figure_dir())
