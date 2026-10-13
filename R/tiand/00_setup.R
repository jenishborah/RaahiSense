# ============================================================
# RaahiSense - TIAND Dataset Analysis
# 00_setup.R
# ============================================================

# ------------------------------------------------------------
# 1. Project paths
# ------------------------------------------------------------

PROJECT_ROOT <- "E:/JB_Mtech_Project/RaahiSense"

RAW_TIAND <- file.path(
  PROJECT_ROOT,
  "data",
  "raw",
  "TIAND_MULTIMODAL_DATASET"
)

R_TIAND <- file.path(
  PROJECT_ROOT,
  "R",
  "tiand"
)

OUTPUT_ROOT <- file.path(
  R_TIAND,
  "outputs"
)

FIGURE_DIR <- file.path(
  OUTPUT_ROOT,
  "figures"
)

TABLE_DIR <- file.path(
  OUTPUT_ROOT,
  "tables"
)

REPORT_DIR <- file.path(
  OUTPUT_ROOT,
  "reports"
)

PROCESSED_DIR <- file.path(
  PROJECT_ROOT,
  "data",
  "processed",
  "tiand"
)

MANIFEST_DIR <- file.path(
  PROJECT_ROOT,
  "data",
  "manifests",
  "tiand"
)


# ------------------------------------------------------------
# 2. Check raw dataset
# ------------------------------------------------------------

if (!dir.exists(RAW_TIAND)) {
  
  stop(
    paste0(
      "TIAND dataset was not found at:\n",
      RAW_TIAND
    )
  )
  
}

cat("TIAND dataset found:\n")
cat(RAW_TIAND, "\n\n")


# ------------------------------------------------------------
# 3. Create analysis output directories
# ------------------------------------------------------------

dir.create(OUTPUT_ROOT, recursive = TRUE, showWarnings = FALSE)
dir.create(FIGURE_DIR, recursive = TRUE, showWarnings = FALSE)
dir.create(TABLE_DIR, recursive = TRUE, showWarnings = FALSE)
dir.create(REPORT_DIR, recursive = TRUE, showWarnings = FALSE)
dir.create(PROCESSED_DIR, recursive = TRUE, showWarnings = FALSE)
dir.create(MANIFEST_DIR, recursive = TRUE, showWarnings = FALSE)


# ------------------------------------------------------------
# Required R packages
# ------------------------------------------------------------

required_packages <- c(
  # Core data handling
  "tidyverse",
  "data.table",
  "janitor",
  "fs",
  
  # Time and date
  "lubridate",
  
  # Visualization
  "ggplot2",
  "scales",
  "patchwork",
  "ggforce",
  "ggstream",
  "ggpattern",
  
  # Spatial analysis
  "sf",
  
  # Relationship/network visualization
  "ggraph",
  "circlize",
  
  # Statistical modelling
  "brms",
  "glmmTMB",
  
  # Reproducible workflow
  "targets",
  
  # Metadata / JSON
  "jsonlite"
)


# ------------------------------------------------------------
# 5. Check installed packages
# ------------------------------------------------------------

installed_packages <- rownames(
  installed.packages()
)

package_status <- data.frame(
  package = required_packages,
  installed = required_packages %in% installed_packages
)

print(package_status)


missing_packages <- package_status$package[
  !package_status$installed
]


# ------------------------------------------------------------
# 6. Report missing packages
# ------------------------------------------------------------

if (length(missing_packages) > 0) {
  
  cat("\nMissing packages:\n")
  print(missing_packages)
  
  cat(
    "\nInstall only the missing packages using:\n\n"
  )
  
  cat(
    "install.packages(c(",
    paste(
      shQuote(missing_packages),
      collapse = ", "
    ),
    "))\n\n"
  )
  
} else {
  
  cat("\nAll required packages are installed.\n")
  
}


# ------------------------------------------------------------
# 7. Basic dataset information
# ------------------------------------------------------------

cat("\n============================================\n")
cat("RaahiSense TIAND Analysis Environment\n")
cat("============================================\n")

cat("Project root:\n", PROJECT_ROOT, "\n\n")
cat("Raw TIAND:\n", RAW_TIAND, "\n\n")
cat("Analysis output:\n", OUTPUT_ROOT, "\n\n")

cat("Raw dataset exists: ", dir.exists(RAW_TIAND), "\n")
cat("Analysis output exists: ", dir.exists(OUTPUT_ROOT), "\n")

cat("\nSetup check complete.\n")