# ============================================================
# RaahiSense | TIAND Dataset Analysis
# 01_dataset_overview.R
#
# Purpose:
#   Build a read-only inventory of the local TIAND dataset.
#   This script inventories files and directory structure only.
#   Folder-name hints are NOT treated as validated modality labels.
#
# Inputs:
#   E:/JB_Mtech_Project/RaahiSense/data/raw/TIAND_MULTIMODAL_DATASET
#
# Outputs:
#   R/tiand/outputs/tables/
#   R/tiand/outputs/figures/
#   data/manifests/tiand/
#
# Raw TIAND files are never modified by this script.
# ============================================================


# ------------------------------------------------------------
# 1. Load project setup
# ------------------------------------------------------------

setup_file <- "E:/JB_Mtech_Project/RaahiSense/R/tiand/00_setup.R"

if (!file.exists(setup_file)) {
  stop(
    "Could not find 00_setup.R at:\n", setup_file,
    "\nUpdate setup_file at the top of this script if your project path differs."
  )
}

source(setup_file)

# Required packages for this script
required_for_inventory <- c("dplyr", "readr", "stringr", "ggplot2", "fs")

missing_for_inventory <- required_for_inventory[
  !vapply(required_for_inventory, requireNamespace, logical(1), quietly = TRUE)
]

if (length(missing_for_inventory) > 0) {
  stop(
    "Install these packages before running the inventory: ",
    paste(missing_for_inventory, collapse = ", "),
    "\nUse install.packages() for the missing packages."
  )
}


# ------------------------------------------------------------
# 2. Validate paths and prepare output directories
# ------------------------------------------------------------

if (!dir.exists(RAW_TIAND)) {
  stop(
    "TIAND raw-data directory does not exist:\n", RAW_TIAND,
    "\nCheck RAW_TIAND in 00_setup.R."
  )
}

dir.create(TABLE_DIR, recursive = TRUE, showWarnings = FALSE)
dir.create(FIGURE_DIR, recursive = TRUE, showWarnings = FALSE)
dir.create(MANIFEST_DIR, recursive = TRUE, showWarnings = FALSE)

cat("\n============================================================\n")
cat("RaahiSense | TIAND Dataset Inventory\n")
cat("============================================================\n")
cat("Raw dataset: ", RAW_TIAND, "\n", sep = "")
cat("Output tables: ", TABLE_DIR, "\n", sep = "")
cat("Output figures: ", FIGURE_DIR, "\n\n", sep = "")


# ------------------------------------------------------------
# 3. Enumerate files and directories
# ------------------------------------------------------------

cat("Scanning files and directories. Large datasets may take time...\n")

# all.files = TRUE includes hidden files where supported.
# no recursion into symbolic links is requested.
all_paths <- list.files(
  path = RAW_TIAND,
  recursive = TRUE,
  all.files = TRUE,
  full.names = TRUE,
  include.dirs = TRUE,
  no.. = TRUE
)

if (length(all_paths) == 0) {
  stop("No files or subdirectories were found under RAW_TIAND.")
}

path_info <- file.info(all_paths)
is_directory <- !is.na(path_info$isdir) & path_info$isdir
is_file <- !is.na(path_info$isdir) & !path_info$isdir

directory_paths <- all_paths[is_directory]
file_paths <- all_paths[is_file]

cat("Paths scanned: ", length(all_paths), "\n", sep = "")
cat("Files found: ", length(file_paths), "\n", sep = "")
cat("Directories found: ", length(directory_paths), "\n\n", sep = "")


# ------------------------------------------------------------
# 4. Create the complete file inventory
# ------------------------------------------------------------

if (length(file_paths) > 0) {
  file_info <- file.info(file_paths)

  relative_paths <- substring(
    normalizePath(file_paths, winslash = "/", mustWork = FALSE),
    nchar(normalizePath(RAW_TIAND, winslash = "/", mustWork = FALSE)) + 2
  )

  normalized_relative <- gsub("\\\\", "/", relative_paths)

  file_inventory <- data.frame(
    relative_path = normalized_relative,
    filename = basename(file_paths),
    directory = dirname(normalized_relative),
    extension = tolower(tools::file_ext(file_paths)),
    size_bytes = as.numeric(file_info$size),
    modified_time = as.character(file_info$mtime),
    stringsAsFactors = FALSE
  )

  file_inventory$extension[
    is.na(file_inventory$extension) | file_inventory$extension == ""
  ] <- "[no extension]"

  file_inventory$size_KB <- file_inventory$size_bytes / 1024
  file_inventory$size_MB <- file_inventory$size_bytes / (1024^2)
  file_inventory$size_GB <- file_inventory$size_bytes / (1024^3)

  # Folder-derived hints only; these are not validated modality labels.
  path_lower <- tolower(file_inventory$relative_path)

  file_inventory$path_hint <- dplyr::case_when(
    grepl("camera|image|video|rgb", path_lower) ~ "Camera/image/video hint",
    grepl("radar", path_lower) ~ "Radar hint",
    grepl("gnss|gps|imu|inertial", path_lower) ~ "GNSS/GPS/IMU hint",
    grepl("lidar|point.?cloud", path_lower) ~ "LiDAR/point-cloud hint",
    grepl("synchroni[sz]ation|timestamp", path_lower) ~ "Synchronization/timestamp hint",
    grepl("calibration", path_lower) ~ "Calibration hint",
    TRUE ~ "Unclassified path"
  )

  file_inventory <- file_inventory |>
    dplyr::arrange(relative_path)

} else {
  file_inventory <- data.frame(
    relative_path = character(),
    filename = character(),
    directory = character(),
    extension = character(),
    size_bytes = numeric(),
    modified_time = character(),
    size_KB = numeric(),
    size_MB = numeric(),
    size_GB = numeric(),
    path_hint = character()
  )
}

readr::write_csv(
  file_inventory,
  file.path(MANIFEST_DIR, "tiand_file_inventory.csv")
)


# ------------------------------------------------------------
# 5. Dataset-level summary
# ------------------------------------------------------------

total_files <- nrow(file_inventory)
total_size_bytes <- sum(file_inventory$size_bytes, na.rm = TRUE)

dataset_summary <- data.frame(
  metric = c(
    "raw_dataset_root",
    "file_count",
    "directory_count",
    "total_size_bytes",
    "total_size_GB",
    "files_with_zero_bytes",
    "files_with_missing_size"
  ),
  value = c(
    RAW_TIAND,
    total_files,
    length(directory_paths),
    format(total_size_bytes, scientific = FALSE, trim = TRUE),
    round(total_size_bytes / (1024^3), 4),
    sum(file_inventory$size_bytes == 0, na.rm = TRUE),
    sum(is.na(file_inventory$size_bytes))
  ),
  stringsAsFactors = FALSE
)

readr::write_csv(
  dataset_summary,
  file.path(TABLE_DIR, "dataset_summary.csv")
)

cat("DATASET SUMMARY\n")
cat("------------------------------\n")
cat("Files: ", format(total_files, big.mark = ","), "\n", sep = "")
cat("Directories: ", format(length(directory_paths), big.mark = ","), "\n", sep = "")
cat("Total size: ", round(total_size_bytes / (1024^3), 4), " GB\n\n", sep = "")


# ------------------------------------------------------------
# 6. Extension counts and size summary
# ------------------------------------------------------------

if (total_files > 0) {
  extension_summary <- file_inventory |>
    dplyr::group_by(extension) |>
    dplyr::summarise(
      file_count = dplyr::n(),
      total_size_bytes = sum(size_bytes, na.rm = TRUE),
      total_size_MB = sum(size_MB, na.rm = TRUE),
      median_size_MB = median(size_MB, na.rm = TRUE),
      largest_file_MB = max(size_MB, na.rm = TRUE),
      .groups = "drop"
    ) |>
    dplyr::mutate(
      file_percentage = 100 * file_count / sum(file_count)
    ) |>
    dplyr::arrange(dplyr::desc(file_count))

  readr::write_csv(
    extension_summary,
    file.path(TABLE_DIR, "dataset_extension_summary.csv")
  )

  size_by_extension <- extension_summary |>
    dplyr::arrange(dplyr::desc(total_size_bytes))

  readr::write_csv(
    size_by_extension,
    file.path(TABLE_DIR, "dataset_size_by_extension.csv")
  )

  cat("FILE COUNTS BY EXTENSION\n")
  print(extension_summary, n = min(nrow(extension_summary), 30))
  cat("\n")
} else {
  extension_summary <- data.frame()
  size_by_extension <- data.frame()
}


# ------------------------------------------------------------
# 7. Folder/path hints (not confirmed modality labels)
# ------------------------------------------------------------

if (total_files > 0) {
  path_hint_summary <- file_inventory |>
    dplyr::group_by(path_hint) |>
    dplyr::summarise(
      file_count = dplyr::n(),
      total_size_MB = sum(size_MB, na.rm = TRUE),
      .groups = "drop"
    ) |>
    dplyr::arrange(dplyr::desc(file_count))

  readr::write_csv(
    path_hint_summary,
    file.path(TABLE_DIR, "dataset_path_hint_summary.csv")
  )

  hint_extension_summary <- file_inventory |>
    dplyr::count(path_hint, extension, name = "file_count") |>
    dplyr::arrange(path_hint, dplyr::desc(file_count))

  readr::write_csv(
    hint_extension_summary,
    file.path(TABLE_DIR, "dataset_path_hint_by_extension.csv")
  )

  cat("PATH HINTS (not validated modality labels)\n")
  print(path_hint_summary)
  cat("\n")
}


# ------------------------------------------------------------
# 8. Directory-level file counts
# ------------------------------------------------------------

if (total_files > 0) {
  directory_summary <- file_inventory |>
    dplyr::group_by(directory) |>
    dplyr::summarise(
      file_count = dplyr::n(),
      total_size_MB = sum(size_MB, na.rm = TRUE),
      .groups = "drop"
    ) |>
    dplyr::arrange(dplyr::desc(file_count))

  readr::write_csv(
    directory_summary,
    file.path(TABLE_DIR, "dataset_directory_summary.csv")
  )
}


# ------------------------------------------------------------
# 9. Largest and smallest files
# ------------------------------------------------------------

if (total_files > 0) {
  largest_files <- file_inventory |>
    dplyr::arrange(dplyr::desc(size_bytes)) |>
    dplyr::select(
      relative_path, path_hint, extension, size_bytes, size_MB, modified_time
    ) |>
    dplyr::slice_head(n = 50)

  smallest_files <- file_inventory |>
    dplyr::arrange(size_bytes) |>
    dplyr::select(
      relative_path, path_hint, extension, size_bytes, size_MB, modified_time
    ) |>
    dplyr::slice_head(n = 50)

  readr::write_csv(largest_files, file.path(TABLE_DIR, "largest_files.csv"))
  readr::write_csv(smallest_files, file.path(TABLE_DIR, "smallest_files.csv"))
}


# ------------------------------------------------------------
# 10. Duplicate filenames and duplicate relative paths
# ------------------------------------------------------------

if (total_files > 0) {
  duplicate_filenames <- file_inventory |>
    dplyr::count(filename, name = "occurrences") |>
    dplyr::filter(occurrences > 1) |>
    dplyr::arrange(dplyr::desc(occurrences), filename)

  duplicate_filename_details <- file_inventory |>
    dplyr::semi_join(duplicate_filenames, by = "filename") |>
    dplyr::arrange(filename, relative_path)

  readr::write_csv(
    duplicate_filenames,
    file.path(TABLE_DIR, "duplicate_filenames_summary.csv")
  )

  readr::write_csv(
    duplicate_filename_details,
    file.path(TABLE_DIR, "duplicate_filename_details.csv")
  )
}


# ------------------------------------------------------------
# 11. Empty directories
# ------------------------------------------------------------

# A directory is considered empty when it has no immediate entries.
# This checks directory contents without deleting or modifying anything.
if (length(directory_paths) > 0) {
  empty_flags <- vapply(
    directory_paths,
    function(p) {
      length(list.files(
        p,
        all.files = TRUE,
        no.. = TRUE,
        recursive = FALSE
      )) == 0
    },
    logical(1)
  )

  empty_directories <- data.frame(
    directory = directory_paths[empty_flags],
    relative_path = substring(
      normalizePath(directory_paths[empty_flags], winslash = "/", mustWork = FALSE),
      nchar(normalizePath(RAW_TIAND, winslash = "/", mustWork = FALSE)) + 2
    ),
    stringsAsFactors = FALSE
  )

} else {
  empty_directories <- data.frame(
    directory = character(),
    relative_path = character()
  )
}

readr::write_csv(
  empty_directories,
  file.path(TABLE_DIR, "empty_directories.csv")
)


# ------------------------------------------------------------
# 12. Directory tree snapshot
# ------------------------------------------------------------

directory_tree <- data.frame(
  relative_path = c(
    ".",
    substring(
      normalizePath(directory_paths, winslash = "/", mustWork = FALSE),
      nchar(normalizePath(RAW_TIAND, winslash = "/", mustWork = FALSE)) + 2
    )
  ),
  stringsAsFactors = FALSE
)

directory_tree <- directory_tree |>
  dplyr::distinct() |>
  dplyr::arrange(relative_path)

readr::write_csv(
  directory_tree,
  file.path(TABLE_DIR, "dataset_directory_tree.csv")
)


# ------------------------------------------------------------
# 13. Plot: file counts by extension
# ------------------------------------------------------------

if (nrow(extension_summary) > 0) {
  plot_extension_data <- extension_summary |>
    dplyr::slice_max(order_by = file_count, n = 25, with_ties = FALSE)

  p_extension <- ggplot2::ggplot(
    plot_extension_data,
    ggplot2::aes(
      x = reorder(extension, file_count),
      y = file_count
    )
  ) +
    ggplot2::geom_col() +
    ggplot2::coord_flip() +
    ggplot2::labs(
      title = "TIAND file count by extension",
      subtitle = "Top 25 extensions; inventory counts, not data-quality results",
      x = "Extension",
      y = "Number of files"
    ) +
    ggplot2::theme_minimal(base_size = 11)

  ggplot2::ggsave(
    file.path(FIGURE_DIR, "dataset_file_count_by_extension.png"),
    plot = p_extension,
    width = 9,
    height = 7,
    dpi = 300
  )

  plot_size_data <- extension_summary |>
    dplyr::slice_max(order_by = total_size_MB, n = 25, with_ties = FALSE)

  p_size <- ggplot2::ggplot(
    plot_size_data,
    ggplot2::aes(
      x = reorder(extension, total_size_MB),
      y = total_size_MB
    )
  ) +
    ggplot2::geom_col() +
    ggplot2::coord_flip() +
    ggplot2::labs(
      title = "TIAND total file size by extension",
      subtitle = "Top 25 extensions by total stored size",
      x = "Extension",
      y = "Total size (MB)"
    ) +
    ggplot2::theme_minimal(base_size = 11)

  ggplot2::ggsave(
    file.path(FIGURE_DIR, "dataset_size_by_extension.png"),
    plot = p_size,
    width = 9,
    height = 7,
    dpi = 300
  )
}


# ------------------------------------------------------------
# 14. Plot: files by path hint
# ------------------------------------------------------------

if (exists("path_hint_summary") && nrow(path_hint_summary) > 0) {
  p_hints <- ggplot2::ggplot(
    path_hint_summary,
    ggplot2::aes(
      x = reorder(path_hint, file_count),
      y = file_count
    )
  ) +
    ggplot2::geom_col() +
    ggplot2::coord_flip() +
    ggplot2::labs(
      title = "TIAND files by folder/path hint",
      subtitle = "Hints are based on path text and must be validated by file inspection",
      x = "Path hint",
      y = "Number of files"
    ) +
    ggplot2::theme_minimal(base_size = 11)

  ggplot2::ggsave(
    file.path(FIGURE_DIR, "dataset_file_count_by_path_hint.png"),
    plot = p_hints,
    width = 10,
    height = 6,
    dpi = 300
  )
}


# ------------------------------------------------------------
# 15. Completion report
# ------------------------------------------------------------

cat("\n============================================================\n")
cat("TIAND INVENTORY COMPLETE\n")
cat("============================================================\n")
cat("Files inventoried: ", format(total_files, big.mark = ","), "\n", sep = "")
cat("Directories found: ", format(length(directory_paths), big.mark = ","), "\n", sep = "")
cat("Empty directories: ", nrow(empty_directories), "\n", sep = "")
cat("Total size (GB): ", round(total_size_bytes / (1024^3), 4), "\n\n", sep = "")

cat("Complete inventory:\n")
cat(file.path(MANIFEST_DIR, "tiand_file_inventory.csv"), "\n\n")

cat("Tables:\n")
cat(TABLE_DIR, "\n\n")

cat("Figures:\n")
cat(FIGURE_DIR, "\n\n")

cat("No raw TIAND files were modified.\n")
cat("IMPORTANT: path hints are not validated sensor/modality classifications.\n")
