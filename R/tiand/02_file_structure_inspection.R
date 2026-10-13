# ============================================================
# RaahiSense | Step 2: TIAND File Structure Inspection
# File: 02_file_structure_inspection.R
#
# Purpose:
#   Inspect actual folders and representative files before
#   starting modality-specific EDA or building an importer.
#
# Input:
#   data/manifests/tiand/tiand_file_inventory.csv
#   Raw TIAND dataset referenced by the inventory's relative paths
#
# Outputs:
#   R/tiand/outputs/inspection/
#     directory_summary.csv
#     extension_summary.csv
#     representative_file_manifest.csv
#     image_inspection.csv
#     tabular_file_inspection.csv
#     timestamp_filename_inspection.csv
#     calibration_file_inspection.csv
#     inspection_notes.txt
#
# Raw data are read only; this script does not modify source files.
# ============================================================

# -----------------------------
# 1. Paths
# -----------------------------
PROJECT_ROOT <- "E:/JB_Mtech_Project/RaahiSense"

INVENTORY_FILE <- file.path(
  PROJECT_ROOT, "data", "manifests", "tiand",
  "tiand_file_inventory.csv"
)

# Set this to the actual dataset root if the inventory uses a different
# relative-path convention. Leave NULL to try common project locations.
DATASET_ROOT_CANDIDATES <- c(
  file.path(PROJECT_ROOT, "data", "raw", "TIAND_MULTIMODAL_DATASET"),
  file.path(PROJECT_ROOT, "data", "TIAND_MULTIMODAL_DATASET"),
  file.path(PROJECT_ROOT, "data", "TINAD_MULTIMODEL_DATASET"),
  file.path(PROJECT_ROOT, "data", "raw", "TINAD_MULTIMODEL_DATASET")
)

OUTPUT_DIR <- file.path(
  PROJECT_ROOT, "R", "tiand", "outputs", "inspection"
)
dir.create(OUTPUT_DIR, recursive = TRUE, showWarnings = FALSE)

if (!file.exists(INVENTORY_FILE)) {
  stop(
    "Inventory CSV not found: ", INVENTORY_FILE,
    "\nRun the TIAND inventory-generation step first, or update INVENTORY_FILE."
  )
}

# -----------------------------
# 2. Packages
# -----------------------------
required_packages <- c("readr", "dplyr", "stringr", "tibble")

missing_packages <- required_packages[
  !vapply(required_packages, requireNamespace, logical(1), quietly = TRUE)
]

if (length(missing_packages) > 0) {
  stop(
    "Install the missing packages first:\ninstall.packages(c(",
    paste(sprintf('"%s"', missing_packages), collapse = ", "),
    "))"
  )
}

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
  library(stringr)
  library(tibble)
})

# Optional packages are used only if already installed.
has_magick <- requireNamespace("magick", quietly = TRUE)
has_jsonlite <- requireNamespace("jsonlite", quietly = TRUE)
has_reticulate <- requireNamespace("reticulate", quietly = TRUE)

# -----------------------------
# 3. Read inventory and resolve dataset root
# -----------------------------
inv <- readr::read_csv(INVENTORY_FILE, show_col_types = FALSE)

required_cols <- c("relative_path", "filename", "directory", "extension")
missing_cols <- setdiff(required_cols, names(inv))
if (length(missing_cols) > 0) {
  stop(
    "Inventory is missing columns: ",
    paste(missing_cols, collapse = ", ")
  )
}

inv <- inv %>%
  mutate(
    relative_path = as.character(relative_path),
    filename = as.character(filename),
    directory = as.character(directory),
    extension = as.character(extension),
    relative_path_clean = str_replace_all(relative_path, "\\\\", "/")
  )

# Find a root by checking which candidate can resolve the most inventory paths.
score_root <- function(root, paths) {
  if (!dir.exists(root)) return(-1L)
  sum(file.exists(file.path(root, paths)), na.rm = TRUE)
}

scores <- vapply(
  DATASET_ROOT_CANDIDATES,
  score_root,
  integer(1),
  paths = inv$relative_path_clean
)

if (length(scores) > 0 && max(scores) > 0) {
  DATASET_ROOT <- DATASET_ROOT_CANDIDATES[which.max(scores)]
  resolved_count <- max(scores)
} else {
  DATASET_ROOT <- NA_character_
  resolved_count <- 0L
}

# If no common candidate worked, inventory paths might already be absolute.
absolute_paths <- file.exists(inv$relative_path_clean)
if (is.na(DATASET_ROOT) && sum(absolute_paths) > 0) {
  inv$resolved_path <- ifelse(
    absolute_paths, inv$relative_path_clean, NA_character_
  )
  resolved_count <- sum(absolute_paths)
} else if (!is.na(DATASET_ROOT)) {
  inv$resolved_path <- file.path(DATASET_ROOT, inv$relative_path_clean)
} else {
  inv$resolved_path <- NA_character_
}

inv$exists_on_disk <- !is.na(inv$resolved_path) & file.exists(inv$resolved_path)

if (all(is.na(DATASET_ROOT))) {
  message(
    "WARNING: Could not resolve the dataset root using the candidate paths.\n",
    "The script will still summarize the inventory, but file-level inspection ",
    "will be limited.\nUpdate DATASET_ROOT_CANDIDATES in the script."
  )
} else {
  message("Resolved dataset root: ", DATASET_ROOT)
}

# -----------------------------
# 4. Directory and extension summaries
# -----------------------------
directory_summary <- inv %>%
  count(directory, name = "file_count", sort = TRUE)

if ("size_bytes" %in% names(inv)) {
  directory_summary <- inv %>%
    group_by(directory) %>%
    summarise(
      file_count = n(),
      total_bytes = sum(as.numeric(size_bytes), na.rm = TRUE),
      .groups = "drop"
    ) %>%
    arrange(desc(file_count))
}

extension_summary <- inv %>%
  count(extension, name = "file_count", sort = TRUE)

if ("size_bytes" %in% names(inv)) {
  extension_summary <- inv %>%
    group_by(extension) %>%
    summarise(
      file_count = n(),
      total_bytes = sum(as.numeric(size_bytes), na.rm = TRUE),
      .groups = "drop"
    ) %>%
    arrange(desc(file_count))
}

readr::write_csv(
  directory_summary,
  file.path(OUTPUT_DIR, "directory_summary.csv")
)
readr::write_csv(
  extension_summary,
  file.path(OUTPUT_DIR, "extension_summary.csv")
)

# -----------------------------
# 5. Select representative files
# -----------------------------
# Select up to 3 existing files per extension, favoring distinct directories.
existing_inv <- inv %>% filter(exists_on_disk)

representatives <- existing_inv %>%
  arrange(extension, directory, filename) %>%
  group_by(extension) %>%
  slice_head(n = 3) %>%
  ungroup() %>%
  select(
    any_of(c(
      "relative_path", "filename", "directory", "extension",
      "size_bytes", "size_MB", "path_hint", "resolved_path"
    ))
  )

readr::write_csv(
  representatives,
  file.path(OUTPUT_DIR, "representative_file_manifest.csv")
)

# -----------------------------
# 6. Inspect images
# -----------------------------
image_rows <- existing_inv %>%
  filter(str_to_lower(extension) %in% c(".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"))

if (nrow(image_rows) > 0) {
  image_rows <- image_rows %>%
    group_by(directory) %>%
    slice_head(n = 3) %>%
    ungroup()

  image_inspection <- lapply(seq_len(nrow(image_rows)), function(i) {
    row <- image_rows[i, ]
    path <- row$resolved_path[[1]]
    width <- NA_real_
    height <- NA_real_
    format <- NA_character_
    readable <- file.exists(path)
    note <- if (readable) "File exists; dimensions not checked" else "Missing file"

    if (readable && has_magick) {
      result <- tryCatch(
        magick::image_info(magick::image_read(path)),
        error = function(e) NULL
      )
      if (!is.null(result) && nrow(result) > 0) {
        width <- result$width[1]
        height <- result$height[1]
        format <- result$format[1]
        note <- "Read successfully with magick"
      } else {
        readable <- FALSE
        note <- "magick could not read image"
      }
    } else if (readable && !has_magick) {
      note <- "File exists; install magick to inspect dimensions/readability"
    }

    tibble(
      relative_path = row$relative_path[[1]],
      directory = row$directory[[1]],
      extension = row$extension[[1]],
      width_px = width,
      height_px = height,
      image_format = format,
      file_readable = readable,
      inspection_note = note
    )
  })

  image_inspection <- bind_rows(image_inspection)
} else {
  image_inspection <- tibble(
    relative_path = character(),
    directory = character(),
    extension = character(),
    width_px = numeric(),
    height_px = numeric(),
    image_format = character(),
    file_readable = logical(),
    inspection_note = character()
  )
}

readr::write_csv(
  image_inspection,
  file.path(OUTPUT_DIR, "image_inspection.csv")
)

# -----------------------------
# 7. Inspect representative CSV/tabular files
# -----------------------------
tabular_rows <- existing_inv %>%
  filter(str_to_lower(extension) %in% c(".csv", ".tsv", ".txt")) %>%
  group_by(directory) %>%
  slice_head(n = 2) %>%
  ungroup()

inspect_table <- function(path, relative_path, extension) {
  result <- tryCatch({
    if (str_to_lower(extension) == ".tsv") {
      dat <- readr::read_tsv(path, n_max = 10, show_col_types = FALSE,
                             progress = FALSE)
    } else {
      dat <- readr::read_csv(path, n_max = 10, show_col_types = FALSE,
                             progress = FALSE)
    }

    tibble(
      relative_path = relative_path,
      file_readable = TRUE,
      column_count = ncol(dat),
      columns = paste(names(dat), collapse = " | "),
      sample_rows_read = nrow(dat),
      first_row_preview = if (nrow(dat) > 0) {
        paste(
          paste(names(dat), as.character(dat[1, ]), sep = "="),
          collapse = " | "
        )
      } else {
        ""
      },
      inspection_note = "Read up to 10 records; source file unchanged"
    )
  }, error = function(e) {
    tibble(
      relative_path = relative_path,
      file_readable = FALSE,
      column_count = NA_integer_,
      columns = NA_character_,
      sample_rows_read = NA_integer_,
      first_row_preview = NA_character_,
      inspection_note = conditionMessage(e)
    )
  })
  result
}

if (nrow(tabular_rows) > 0) {
  tabular_inspection <- bind_rows(lapply(seq_len(nrow(tabular_rows)), function(i) {
    inspect_table(
      tabular_rows$resolved_path[[i]],
      tabular_rows$relative_path[[i]],
      tabular_rows$extension[[i]]
    )
  }))
} else {
  tabular_inspection <- tibble(
    relative_path = character(),
    file_readable = logical(),
    column_count = integer(),
    columns = character(),
    sample_rows_read = integer(),
    first_row_preview = character(),
    inspection_note = character()
  )
}

readr::write_csv(
  tabular_inspection,
  file.path(OUTPUT_DIR, "tabular_file_inspection.csv")
)

# -----------------------------
# 8. Inspect filename timestamps
# -----------------------------
# Only detects common clock-like patterns. It does not assume a date,
# timezone, epoch, or cross-sensor synchronization.
timestamp_inspection <- inv %>%
  mutate(
    filename_timestamp = str_extract(
      filename,
      "(?<![0-9])[0-2]?[0-9]-[0-5][0-9]-[0-5][0-9](\\.[0-9]+)?"
    ),
    timestamp_pattern_found = !is.na(filename_timestamp),
    timestamp_parse_status = case_when(
      is.na(filename_timestamp) ~ "No common HH-MM-SS pattern detected",
      TRUE ~ "Candidate pattern detected; meaning not yet validated"
    )
  ) %>%
  select(
    any_of(c(
      "relative_path", "filename", "directory", "extension",
      "filename_timestamp", "timestamp_pattern_found",
      "timestamp_parse_status"
    ))
  )

readr::write_csv(
  timestamp_inspection,
  file.path(OUTPUT_DIR, "timestamp_filename_inspection.csv")
)

# -----------------------------
# 9. Inspect calibration-related files
# -----------------------------
calibration_rows <- existing_inv %>%
  filter(
    str_detect(str_to_lower(relative_path), "calibration|calib") |
      str_to_lower(extension) %in% c(".json", ".npy")
  )

calibration_inspection <- lapply(seq_len(nrow(calibration_rows)), function(i) {
  row <- calibration_rows[i, ]
  path <- row$resolved_path[[1]]
  ext <- str_to_lower(row$extension[[1]])
  preview <- ""
  status <- "File exists; contents not parsed"

  if (ext == ".json" && has_jsonlite) {
    obj <- tryCatch(jsonlite::fromJSON(path, simplifyVector = FALSE),
                    error = function(e) e)
    if (inherits(obj, "error")) {
      status <- paste("JSON parse error:", conditionMessage(obj))
    } else {
      preview <- paste(utils::head(names(obj), 30), collapse = " | ")
      status <- "JSON parsed; top-level keys listed"
    }
  } else if (ext == ".json" && !has_jsonlite) {
    status <- "Install jsonlite to parse JSON"
  } else if (ext == ".npy") {
    status <- if (has_reticulate) {
      "NumPy file found; Python/NumPy parsing not attempted automatically"
    } else {
      "NumPy file found; inspect later with Python/NumPy"
    }
  }

  tibble(
    relative_path = row$relative_path[[1]],
    extension = row$extension[[1]],
    size_bytes = if ("size_bytes" %in% names(row)) as.numeric(row$size_bytes[[1]]) else NA_real_,
    content_preview = preview,
    inspection_status = status
  )
})

if (length(calibration_inspection) > 0) {
  calibration_inspection <- bind_rows(calibration_inspection)
} else {
  calibration_inspection <- tibble(
    relative_path = character(),
    extension = character(),
    size_bytes = numeric(),
    content_preview = character(),
    inspection_status = character()
  )
}

readr::write_csv(
  calibration_inspection,
  file.path(OUTPUT_DIR, "calibration_file_inspection.csv")
)

# -----------------------------
# 10. Write human-readable notes
# -----------------------------
timestamp_count <- sum(timestamp_inspection$timestamp_pattern_found, na.rm = TRUE)
missing_on_disk <- sum(!inv$exists_on_disk, na.rm = TRUE)

notes <- c(
  "RaahiSense - TIAND file structure inspection",
  paste0("Inventory CSV: ", INVENTORY_FILE),
  paste0("Inventory rows: ", nrow(inv)),
  paste0("Files resolved on disk: ", sum(inv$exists_on_disk, na.rm = TRUE)),
  paste0("Inventory paths not resolved: ", missing_on_disk),
  paste0("Filename clock-like patterns detected: ", timestamp_count),
  paste0("Image candidates inspected: ", nrow(image_inspection)),
  paste0("Tabular files sampled: ", nrow(tabular_inspection)),
  paste0("Calibration/JSON/NPY files inspected: ", nrow(calibration_inspection)),
  "",
  "Important interpretation limits:",
  "- Folder names and file extensions are hints, not proof of sensor semantics.",
  "- Filename timestamp patterns are candidates; date, timezone, units, and clock origin remain unverified.",
  "- Existing timestamps do not prove cross-sensor synchronization.",
  "- Only a limited sample of CSV files is read; full schemas may vary between files.",
  "- Raw dataset files were not written to or modified by this script.",
  "",
  "Optional packages:",
  paste0("magick installed: ", has_magick),
  paste0("jsonlite installed: ", has_jsonlite),
  paste0("reticulate installed: ", has_reticulate)
)

writeLines(notes, file.path(OUTPUT_DIR, "inspection_notes.txt"))

# -----------------------------
# 11. Console summary
# -----------------------------
cat("\nTIAND file structure inspection completed.\n")
cat("Inventory rows: ", nrow(inv), "\n", sep = "")
cat("Resolved files: ", sum(inv$exists_on_disk, na.rm = TRUE), "\n", sep = "")
cat("Unresolved paths: ", missing_on_disk, "\n", sep = "")
cat("Image samples inspected: ", nrow(image_inspection), "\n", sep = "")
cat("Tabular samples inspected: ", nrow(tabular_inspection), "\n", sep = "")
cat("Filename timestamp candidates: ", timestamp_count, "\n", sep = "")
cat("Output directory: ", OUTPUT_DIR, "\n", sep = "")
cat("\nReview the CSV outputs before moving to camera-specific EDA.\n")
