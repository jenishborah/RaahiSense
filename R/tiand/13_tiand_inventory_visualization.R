# ============================================================
# RaahiSense | TIAND Advanced Inventory Visualization
# File: 13_tiand_inventory_visualization.R
#
# Input:
#   data/manifests/tiand/tiand_file_inventory.csv
#
# Output:
#   R/tiand/outputs/figures/tiand_inventory_advanced.png
#   R/tiand/outputs/figures/tiand_inventory_advanced.pdf
#   Three supporting summary CSV files
#
# Required packages:
#   ggplot2, dplyr, readr, stringr, scales, patchwork
#
# This script reads the inventory CSV only. It does not modify
# the raw TIAND dataset. It intentionally avoids optional
# pattern/geometric packages to improve reproducibility.
# ============================================================

# -----------------------------
# 1. Paths
# -----------------------------
PROJECT_ROOT <- "E:/JB_Mtech_Project/RaahiSense"

INVENTORY_FILE <- file.path(
  PROJECT_ROOT, "data", "manifests", "tiand",
  "tiand_file_inventory.csv"
)

FIGURE_DIR <- file.path(
  PROJECT_ROOT, "R", "tiand", "outputs", "figures"
)

dir.create(FIGURE_DIR, recursive = TRUE, showWarnings = FALSE)

if (!file.exists(INVENTORY_FILE)) {
  stop(
    "Inventory CSV not found:\n", INVENTORY_FILE,
    "\nEdit INVENTORY_FILE so it points to your tiand_file_inventory.csv."
  )
}

# -----------------------------
# 2. Check and load packages
# -----------------------------
required_packages <- c(
  "ggplot2", "dplyr", "readr", "stringr", "scales", "patchwork"
)

missing_packages <- required_packages[
  !vapply(required_packages, requireNamespace, logical(1), quietly = TRUE)
]

if (length(missing_packages) > 0) {
  stop(
    "Missing package(s): ", paste(missing_packages, collapse = ", "),
    "\nInstall them with:\ninstall.packages(c(",
    paste(sprintf('"%s"', missing_packages), collapse = ", "),
    "))"
  )
}

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(readr)
  library(stringr)
  library(scales)
  library(patchwork)
})

# -----------------------------
# 3. Read and validate inventory
# -----------------------------
inv <- readr::read_csv(INVENTORY_FILE, show_col_types = FALSE)

required_cols <- c(
  "relative_path", "filename", "directory", "extension",
  "size_bytes", "size_MB", "path_hint"
)

missing_cols <- setdiff(required_cols, names(inv))
if (length(missing_cols) > 0) {
  stop(
    "Inventory is missing required column(s): ",
    paste(missing_cols, collapse = ", "),
    "\nColumns found: ", paste(names(inv), collapse = ", ")
  )
}

inv <- inv %>%
  mutate(
    extension = if_else(
      is.na(extension) | str_trim(as.character(extension)) == "",
      "[no extension]", as.character(extension)
    ),
    directory = if_else(
      is.na(directory) | str_trim(as.character(directory)) == "",
      "[root directory]", as.character(directory)
    ),
    relative_path = as.character(relative_path),
    path_hint = if_else(
      is.na(path_hint) | str_trim(as.character(path_hint)) == "",
      "Unclassified path", as.character(path_hint)
    ),
    size_bytes = suppressWarnings(as.numeric(size_bytes)),
    size_MB_input = suppressWarnings(as.numeric(size_MB)),
    size_MB = if_else(
      is.na(size_MB_input) & !is.na(size_bytes),
      size_bytes / (1024^2),
      size_MB_input
    ),
    size_GiB = size_bytes / (1024^3),
    path_lower = str_to_lower(str_replace_all(relative_path, "\\\\", "/")),
    # Folder-name classification only. This does not verify sensor semantics.
    category = case_when(
      str_detect(path_lower, "calibration") ~ "Calibration",
      str_detect(path_lower, "synchroni[sz]ation|timestamp") ~ "Synchronization",
      str_detect(path_lower, "(^|/)camera(/|_)") ~ "Camera path",
      str_detect(path_lower, "(^|/)radar(/|_)") ~ "Radar path",
      str_detect(path_lower, "(^|/)gnss(/|_)") ~ "GNSS path",
      str_detect(path_lower, "lidar|point.?cloud") ~ "LiDAR-related path",
      TRUE ~ "Other"
    )
  ) %>%
  select(-size_MB_input, -path_lower)

if (nrow(inv) == 0) {
  stop("The inventory CSV contains no rows. Check the input file.")
}

# -----------------------------
# 4. Calculate inventory metrics
# -----------------------------
n_files <- nrow(inv)
total_bytes <- sum(inv$size_bytes, na.rm = TRUE)
total_gib <- total_bytes / (1024^3)
n_dirs <- dplyr::n_distinct(inv$directory)
n_ext <- dplyr::n_distinct(inv$extension)
n_zero <- sum(inv$size_bytes == 0, na.rm = TRUE)

# Human-readable file-size labels without relying on label_bytes().
format_bytes <- function(x) {
  vapply(x, function(value) {
    if (is.na(value)) return(NA_character_)
    if (value >= 1024^3) return(sprintf("%.2f GiB", value / 1024^3))
    if (value >= 1024^2) return(sprintf("%.1f MiB", value / 1024^2))
    if (value >= 1024) return(sprintf("%.1f KiB", value / 1024))
    sprintf("%.0f B", value)
  }, character(1))
}

ext_summary <- inv %>%
  group_by(extension) %>%
  summarise(
    files = n(),
    total_MB = sum(size_MB, na.rm = TRUE),
    median_MB = median(size_MB, na.rm = TRUE),
    .groups = "drop"
  ) %>%
  mutate(
    pct_files = files / sum(files),
    pct_storage = if (sum(total_MB, na.rm = TRUE) > 0) {
      total_MB / sum(total_MB, na.rm = TRUE)
    } else {
      0
    }
  ) %>%
  arrange(desc(files))

top_ext <- ext_summary %>%
  slice_max(order_by = files, n = 12, with_ties = FALSE) %>%
  mutate(extension = reorder(extension, files))

storage_ext <- ext_summary %>%
  slice_max(order_by = total_MB, n = 10, with_ties = FALSE) %>%
  mutate(extension = reorder(extension, total_MB))

folder_summary <- inv %>%
  group_by(directory) %>%
  summarise(
    files = n(),
    total_MB = sum(size_MB, na.rm = TRUE),
    .groups = "drop"
  ) %>%
  arrange(desc(files))

top_folders <- folder_summary %>%
  slice_head(n = 12) %>%
  mutate(
    directory_label = str_trunc(directory, 52),
    directory_label = reorder(directory_label, files)
  )

category_summary <- inv %>%
  group_by(category) %>%
  summarise(
    files = n(),
    total_MB = sum(size_MB, na.rm = TRUE),
    .groups = "drop"
  ) %>%
  arrange(desc(files)) %>%
  mutate(category = reorder(category, files))

# -----------------------------
# 5. Theme and palette
# -----------------------------
theme_raahi <- theme_minimal(base_size = 11) +
  theme(
    plot.title = element_text(face = "bold", size = 13, colour = "#172033"),
    plot.subtitle = element_text(size = 9, colour = "#5B6474"),
    axis.title = element_text(face = "bold", colour = "#374151"),
    axis.text = element_text(colour = "#374151"),
    panel.grid.minor = element_blank(),
    panel.grid.major.y = element_blank(),
    plot.background = element_rect(fill = "white", colour = NA),
    panel.background = element_rect(fill = "white", colour = NA),
    plot.margin = margin(10, 14, 10, 10)
  )

raahi_blue <- "#2F6690"
raahi_teal <- "#3A7D78"
raahi_orange <- "#D9822B"
raahi_purple <- "#7868A6"
raahi_grey <- "#A7AFBA"

# -----------------------------
# 6. KPI cards
# -----------------------------
kpi_data <- data.frame(
  x = 1:4,
  label = c(
    "FILES INVENTORIED",
    "TOTAL STORAGE",
    "DIRECTORY PATHS",
    "FILE EXTENSIONS"
  ),
  value = c(
    comma(n_files),
    paste0(format(round(total_gib, 2), nsmall = 2), " GiB"),
    comma(n_dirs),
    comma(n_ext)
  )
)

p_kpi <- ggplot(kpi_data, aes(x = x, y = 1)) +
  geom_tile(
    aes(fill = factor(x)),
    width = 0.94, height = 0.82,
    colour = "#E1E6ED", linewidth = 0.6
  ) +
  geom_text(
    aes(label = value),
    y = 1.08, size = 6, fontface = "bold",
    colour = "#172033"
  ) +
  geom_text(
    aes(label = label),
    y = 0.78, size = 2.8, fontface = "bold",
    colour = "#586174"
  ) +
  scale_fill_manual(
    values = c("1" = "#F4F7FA", "2" = "#F4F7FA",
               "3" = "#F4F7FA", "4" = "#F4F7FA"),
    guide = "none"
  ) +
  coord_cartesian(ylim = c(0.55, 1.35), clip = "off") +
  theme_void() +
  theme(plot.margin = margin(4, 4, 4, 4))

# -----------------------------
# 7. File count by extension
# -----------------------------
p_ext_count <- ggplot(top_ext, aes(x = extension, y = files)) +
  geom_col(fill = raahi_blue, width = 0.72) +
  geom_text(
    aes(label = comma(files)), hjust = -0.12, size = 3.1,
    colour = "#263244"
  ) +
  coord_flip() +
  scale_y_continuous(
    labels = comma,
    expand = expansion(mult = c(0, 0.18))
  ) +
  labs(
    title = "File count by extension",
    subtitle = "Top 12 extensions; all extensions remain in the inventory CSV",
    x = NULL, y = "Files"
  ) +
  theme_raahi

# -----------------------------
# 8. Storage by extension
# -----------------------------
p_ext_storage <- ggplot(storage_ext, aes(x = extension, y = total_MB)) +
  geom_col(fill = raahi_teal, width = 0.72) +
  geom_text(
    aes(label = paste0(comma(round(total_MB)), " MB")),
    hjust = -0.12, size = 3.0, colour = "#263244"
  ) +
  coord_flip() +
  scale_y_continuous(
    labels = label_number(big.mark = ","),
    expand = expansion(mult = c(0, 0.23))
  ) +
  labs(
    title = "Storage by extension",
    subtitle = "File types contributing to the total stored volume",
    x = NULL, y = "Total size (MB)"
  ) +
  theme_raahi

# -----------------------------
# 9. Top folders by file count
# -----------------------------
p_folders <- ggplot(top_folders, aes(x = directory_label, y = files)) +
  geom_col(fill = raahi_purple, width = 0.72) +
  geom_text(
    aes(label = comma(files)), hjust = -0.12, size = 2.9,
    colour = "#263244"
  ) +
  coord_flip() +
  scale_y_continuous(
    labels = comma,
    expand = expansion(mult = c(0, 0.18))
  ) +
  labs(
    title = "Directories with the most files",
    subtitle = "Top 12 directory paths in the inventory",
    x = NULL, y = "Files"
  ) +
  theme_raahi

# -----------------------------
# 10. Folder-derived path categories
# -----------------------------
# Uses standard ggplot2 bars only; no ggpattern dependency.
p_category <- ggplot(category_summary, aes(x = category, y = files)) +
  geom_col(fill = raahi_orange, width = 0.72) +
  geom_text(
    aes(label = comma(files)), hjust = -0.12, size = 3.0,
    colour = "#263244"
  ) +
  coord_flip() +
  scale_y_continuous(
    labels = comma,
    expand = expansion(mult = c(0, 0.18))
  ) +
  labs(
    title = "Files by path-derived category",
    subtitle = "Preliminary folder-name classification, not verified sensor content",
    x = NULL, y = "Files"
  ) +
  theme_raahi

# -----------------------------
# 11. File-size distribution
# -----------------------------
# Zero-byte files are excluded from the log-scale histogram.
size_data <- inv %>%
  filter(!is.na(size_bytes), is.finite(size_bytes), size_bytes > 0)

p_size_dist <- ggplot(size_data, aes(x = size_bytes)) +
  geom_histogram(
    bins = 45, fill = raahi_blue, colour = "white", linewidth = 0.25
  ) +
  scale_x_log10(labels = format_bytes) +
  labs(
    title = "Distribution of file sizes",
    subtitle = paste0(
      "Logarithmic x-axis; ", comma(n_zero),
      " zero-byte file(s) excluded from this panel"
    ),
    x = "File size (log scale)", y = "Number of files"
  ) +
  theme_raahi

# -----------------------------
# 12. Compose dashboard
# -----------------------------
header <- patchwork::plot_annotation(
  title = "RAAHISENSE | TIAND DATASET INVENTORY",
  subtitle = paste0(
    "Local file inventory • ", scales::comma(n_files), " files • ",
    format(round(total_gib, 2), nsmall = 2),
    " GiB reported storage • Generated from tiand_file_inventory.csv"
  ),
  caption = paste(
    "Interpretation note: folder-derived categories are preliminary hints, not validated modality labels.",
    "This report describes files and storage only; it does not establish data quality, timestamp validity,",
    "sensor synchronization, or measurement completeness."
  ),
  theme = ggplot2::theme(
    plot.title = ggplot2::element_text(size = 19, face = "bold", colour = "#172033"),
    plot.subtitle = ggplot2::element_text(size = 10, colour = "#586174"),
    plot.caption = ggplot2::element_text(size = 8, colour = "#586174", hjust = 0),
    plot.background = ggplot2::element_rect(fill = "white", colour = NA)
  )
)

# Compose the panels using patchwork's operators.
# plot_annotation() is metadata and must be added to a patchwork object,
# not used as the left-hand side of the '/' composition operator.
dashboard <- (
  p_kpi /
  (p_ext_count | p_ext_storage) /
  (p_folders | p_category) /
  p_size_dist
)

dashboard <- dashboard +
  patchwork::plot_layout(heights = c(0.75, 2.1, 2.1, 1.5))

dashboard <- dashboard & theme_raahi

# plot_annotation() adds a title/subtitle/caption to the patchwork;
# it does not create a separate plot row. Do not override the dashboard's
# internal row heights here, otherwise the panels can be compressed or appear blank.
final_plot <- dashboard + header

# -----------------------------
# 13. Save high-resolution outputs
# -----------------------------
png_file <- file.path(FIGURE_DIR, "tiand_inventory_advanced.png")
pdf_file <- file.path(FIGURE_DIR, "tiand_inventory_advanced.pdf")

ggsave(
  filename = png_file,
  plot = final_plot,
  width = 16,
  height = 18,
  units = "in",
  dpi = 320,
  bg = "white",
  limitsize = FALSE
)

# Prefer Cairo PDF where supported; fall back to the standard PDF device.
pdf_saved <- tryCatch({
  ggsave(
    filename = pdf_file,
    plot = final_plot,
    width = 16,
    height = 18,
    units = "in",
    device = grDevices::cairo_pdf,
    bg = "white",
    limitsize = FALSE
  )
  TRUE
}, error = function(e) {
  message("Cairo PDF device unavailable; using standard PDF device. Details: ",
          conditionMessage(e))
  tryCatch({
    ggsave(
      filename = pdf_file,
      plot = final_plot,
      width = 16,
      height = 18,
      units = "in",
      device = "pdf",
      bg = "white",
      limitsize = FALSE
    )
    TRUE
  }, error = function(e2) {
    warning("Could not create PDF: ", conditionMessage(e2))
    FALSE
  })
})

# -----------------------------
# 14. Export supporting summaries
# -----------------------------
readr::write_csv(
  ext_summary,
  file.path(FIGURE_DIR, "visualization_extension_summary.csv")
)
readr::write_csv(
  folder_summary,
  file.path(FIGURE_DIR, "visualization_directory_summary.csv")
)
readr::write_csv(
  category_summary,
  file.path(FIGURE_DIR, "visualization_path_category_summary.csv")
)

# -----------------------------
# 15. Completion report
# -----------------------------
cat("\nTIAND advanced inventory visualization completed.\n")
cat("Input inventory: ", INVENTORY_FILE, "\n", sep = "")
cat("Files inventoried: ", comma(n_files), "\n", sep = "")
cat("Total storage: ", format(round(total_gib, 3), nsmall = 3), " GiB\n", sep = "")
cat("Distinct directory paths: ", comma(n_dirs), "\n", sep = "")
cat("Distinct extensions: ", comma(n_ext), "\n", sep = "")
cat("Zero-byte files: ", comma(n_zero), "\n", sep = "")
cat("PNG: ", png_file, "\n", sep = "")
cat("PDF: ", if (pdf_saved) pdf_file else "Not created; see warning above", "\n", sep = "")
cat("Summary CSVs saved in: ", FIGURE_DIR, "\n", sep = "")
cat("\nNote: path-derived categories are preliminary and do not verify sensor content.\n")
