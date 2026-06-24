## theme_paper.R
## Publication-grade theme for AJPM/Lancet-style manuscript figures.
## Design choices:
##   - Sans-serif system font (Arial/Helvetica), tight metrics
##   - Single thin axis line at 0.4 pt; no panel border; very faint y-grid only
##   - No subtitles inside panels; panel labels via tag = "A","B","C" (bold capital)
##   - Sex palette: deep navy (Male) and deep red (Female), Lancet/NEJM inspired
##   - Direct value labels on bars where space allows; legends above plot, no key box

suppressPackageStartupMessages({
  library(ggplot2)
  library(scales)
})

## Lancet/NEJM-inspired palette (dark, saturated, colorblind-friendly).
lancet_palette <- c(
  navy   = "#0F2A47",
  red    = "#9B1B30",
  teal   = "#0C7C8A",
  amber  = "#C26100",
  steel  = "#3B6E8F",
  ash    = "#5A5A5A"
)

sex_palette <- c(
  Female = unname(lancet_palette["red"]),
  Male   = unname(lancet_palette["navy"])
)

model_palette <- c(
  Main     = unname(lancet_palette["navy"]),
  `24-month lagged` = unname(lancet_palette["red"])
)

scenario_palette <- c(
  `Main HR (age-sex)` = unname(lancet_palette["navy"]),
  `24-month lagged HR` = unname(lancet_palette["red"]),
  `Overall PAF`       = unname(lancet_palette["teal"])
)

## Base theme.
theme_paper <- function(base_size = 8.5) {
  theme_classic(base_size = base_size, base_family = "sans") +
    theme(
      plot.title           = element_blank(),
      plot.subtitle        = element_blank(),
      plot.tag             = element_text(face = "bold", size = base_size + 1.5,
                                           family = "sans"),
      plot.tag.position    = c(0.005, 0.985),
      plot.caption         = element_text(size = base_size - 1, color = "grey25",
                                           hjust = 0, margin = margin(t = 4)),
      axis.title           = element_text(size = base_size, color = "black"),
      axis.text            = element_text(size = base_size - 0.5, color = "black"),
      axis.line            = element_line(color = "black", linewidth = 0.35),
      axis.ticks           = element_line(color = "black", linewidth = 0.3),
      axis.ticks.length    = unit(2.5, "pt"),
      panel.grid.major.y   = element_line(color = "grey92", linewidth = 0.25),
      panel.grid.major.x   = element_blank(),
      panel.grid.minor     = element_blank(),
      panel.border         = element_blank(),
      strip.text           = element_blank(),
      strip.background     = element_blank(),
      legend.title         = element_blank(),
      legend.text          = element_text(size = base_size - 0.5, color = "black"),
      legend.key.size      = unit(0.4, "cm"),
      legend.key           = element_blank(),
      legend.background    = element_blank(),
      legend.position      = "top",
      legend.justification = "left",
      legend.box.spacing   = unit(0.0, "cm"),
      legend.margin        = margin(0, 0, 2, 0),
      plot.margin          = margin(8, 10, 6, 6)
    )
}

## Save with PDF (cairo, fonts embedded) and 600 dpi PNG.
## Wraps the PDF write in tryCatch so a locked viewer does not abort the
## script before the PNG is written.
save_figure <- function(plot, basename, width_in, height_in, dpi = 600) {
  out_dir <- file.path("outputs", "figures", "manuscript")
  if (!dir.exists(out_dir)) dir.create(out_dir, recursive = TRUE)
  pdf_path <- file.path(out_dir, paste0(basename, ".pdf"))
  png_path <- file.path(out_dir, paste0(basename, ".png"))
  tryCatch(
    ggsave(
      filename = pdf_path, plot = plot,
      width = width_in, height = height_in, units = "in",
      device = cairo_pdf
    ),
    error = function(e) {
      message("PDF write failed for ", basename, ": ", conditionMessage(e),
              " - continuing with PNG only.")
    }
  )
  ggsave(
    filename = png_path, plot = plot,
    width = width_in, height = height_in, units = "in",
    dpi = dpi
  )
  invisible(NULL)
}

pcd_figure_dir <- function() {
  out_dir <- file.path("submission_pcd", "figures")
  dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
  out_dir
}

pcd_eps_device <- function(filename, width, height, ...) {
  if (capabilities("cairo")) {
    grDevices::cairo_ps(
      filename = filename, width = width, height = height,
      onefile = FALSE, fallback_resolution = 600, ...
    )
  } else {
    grDevices::postscript(
      file = filename, width = width, height = height,
      onefile = FALSE, horizontal = FALSE, paper = "special",
      family = "Helvetica", ...
    )
  }
}

save_pcd_figure <- function(plot, filename_base, width_in, height_in) {
  out_dir <- pcd_figure_dir()
  pdf_path <- file.path(out_dir, paste0(filename_base, ".pdf"))
  svg_path <- file.path(out_dir, paste0(filename_base, "_original.svg"))
  eps_path <- file.path(out_dir, paste0(filename_base, "_original.eps"))

  ggsave(
    filename = pdf_path, plot = plot,
    width = width_in, height = height_in, units = "in",
    device = cairo_pdf
  )

  svg_ok <- FALSE
  svg_error <- NULL
  svg_device <- if (requireNamespace("svglite", quietly = TRUE)) {
    function(filename, width, height, ...) {
      svglite::svglite(file = filename, width = width, height = height, ...)
    }
  } else if (capabilities("cairo")) {
    grDevices::svg
  } else {
    NULL
  }

  if (!is.null(svg_device)) {
    svg_ok <- tryCatch(
      {
        ggsave(
          filename = svg_path, plot = plot,
          width = width_in, height = height_in, units = "in",
          device = svg_device
        )
        TRUE
      },
      error = function(e) {
        svg_error <<- conditionMessage(e)
        FALSE
      }
    )
  }

  if (svg_ok) {
    native_path <- svg_path
  } else {
    if (file.exists(svg_path)) unlink(svg_path)
    if (!is.null(svg_error)) {
      message("SVG write failed for ", filename_base, ": ", svg_error,
              " - writing EPS instead.")
    } else {
      message("SVG device unavailable for ", filename_base,
              " - writing EPS instead.")
    }
    ggsave(
      filename = eps_path, plot = plot,
      width = width_in, height = height_in, units = "in",
      device = pcd_eps_device
    )
    native_path <- eps_path
  }

  list(
    figure = filename_base,
    native_path = native_path,
    pdf_path = pdf_path
  )
}

export_pcd_existing_vector_figure <- function(source_pdf, filename_base) {
  out_dir <- pcd_figure_dir()
  if (!file.exists(source_pdf)) {
    stop("Source PDF not found: ", source_pdf, call. = FALSE)
  }

  pdf_path <- file.path(out_dir, paste0(filename_base, ".pdf"))
  svg_path <- file.path(out_dir, paste0(filename_base, "_original.svg"))
  eps_path <- file.path(out_dir, paste0(filename_base, "_original.eps"))

  file.copy(source_pdf, pdf_path, overwrite = TRUE)

  dvisvgm <- Sys.which("dvisvgm")
  svg_ok <- FALSE
  if (nzchar(dvisvgm)) {
    status <- system2(
      dvisvgm,
      args = c("--pdf", "-o", svg_path, source_pdf),
      stdout = TRUE,
      stderr = TRUE
    )
    svg_ok <- identical(attr(status, "status"), NULL) && file.exists(svg_path)
    if (!svg_ok && file.exists(svg_path)) unlink(svg_path)
  }

  if (svg_ok) {
    native_path <- svg_path
  } else {
    pdftops <- Sys.which("pdftops")
    if (!nzchar(pdftops)) {
      stop(
        "Could not create SVG with dvisvgm and pdftops is unavailable for EPS fallback.",
        call. = FALSE
      )
    }
    status <- system2(
      pdftops,
      args = c("-eps", source_pdf, eps_path),
      stdout = TRUE,
      stderr = TRUE
    )
    eps_ok <- identical(attr(status, "status"), NULL) && file.exists(eps_path)
    if (!eps_ok) {
      stop("Could not create SVG or EPS for ", filename_base, call. = FALSE)
    }
    native_path <- eps_path
  }

  list(
    figure = filename_base,
    native_path = native_path,
    pdf_path = pdf_path
  )
}

write_pcd_manifest <- function(records,
                               path = file.path(pcd_figure_dir(),
                                                "FIGURE_FILES_FOR_PCD.txt")) {
  rel_path <- function(x) {
    gsub("\\\\", "/", x)
  }

  lines <- c(
    "Figure files for PCD resubmission PCD-26-0311",
    "",
    "Upload each figure as two separate files in ScholarOne.",
    "Figure captions/legends remain in the manuscript Word file.",
    ""
  )

  for (record in records) {
    lines <- c(
      lines,
      paste0(record$figure, ":"),
      paste0("  Original/native vector: ", rel_path(record$native_path)),
      paste0("  PDF: ", rel_path(record$pdf_path)),
      ""
    )
  }

  writeLines(lines, path, useBytes = TRUE)
  invisible(path)
}

age_levels_5 <- c("30-34", "35-44", "45-54", "55-64", "65-69")
sex_levels   <- c("Female", "Male")
freq_levels  <- c("0", "1", "2", "3-4", "5+")
