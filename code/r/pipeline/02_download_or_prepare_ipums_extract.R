source(file.path("code", "r", "lib", "msaburden.R"))

ensure_standard_dirs()
samples <- paste0("ih", 1997:2018)
variables <- c(
  "YEAR", "SERIAL", "NHISPID", "QUARTER", "ASTATFLG", "STRATA", "PSU",
  "SAMPWEIGHT", "PERWEIGHT", "MORTWT", "MORTWTSA", "MORTELIG", "MORTSTAT",
  "MORTDODY", "MORTDODQ", "MORTUCODLD", "MORTUCOD", "STRONGFNO",
  "STRONGFTP", "STRONGFWK", "MOD10FNO", "MOD10FTP", "MOD10FWK",
  "MOD10DNO", "MOD10DTP", "MOD10DMIN", "VIG10FNO", "VIG10FTP",
  "VIG10FWK", "VIG10DNO", "VIG10DTP", "VIG10DMIN", "AGE", "SEX",
  "RACEA", "HISPETH", "EDUC", "POVERTY", "MARSTAT", "REGION",
  "BMICALC", "SMOKESTATUS2", "ALCSTAT1", "ALCSTAT2", "HEALTH",
  "DIABETICEV", "HYPERTENEV", "CHEARTDIEV", "HEARTATTEV", "STROKEV",
  "CANCEREV"
)

payload <- list(
  description = "MSA burden US: NHIS 1997-2018 linked mortality extract for MSA dose-response prep",
  dataStructure = list(rectangular = list(on = "P")),
  dataFormat = "csv",
  samples = stats::setNames(vector("list", length(samples)), samples),
  variables = stats::setNames(vector("list", length(variables)), variables)
)

payload_path <- here("data", "raw", "ipums_nhis_extract_payload.json")
if (requireNamespace("jsonlite", quietly = TRUE)) {
  write_text(payload_path, jsonlite::toJSON(payload, auto_unbox = TRUE, pretty = TRUE))
} else {
  write_text(payload_path, paste0(
    "{\n",
    '  "description": "', payload$description, '",\n',
    '  "dataFormat": "csv",\n',
    '  "samples": [', paste(sprintf('"%s"', samples), collapse = ", "), "],\n",
    '  "variables": [', paste(sprintf('"%s"', variables), collapse = ", "), "]\n",
    "}\n"
  ))
}

sources <- c(
  "IPUMS API microdata docs: https://developer.ipums.org/docs/v2/apiprogram/apis/microdata/",
  "IPUMS API extract workflow: https://developer.ipums.org/docs/v2/workflows/create_extracts/microdata/",
  "IPUMS NHIS sample IDs: https://nhis.ipums.org/nhis-action/samples/sample_ids",
  "IPUMS NHIS mortality variables: https://nhis.ipums.org/nhis-action/variables/group/mortality_mortality",
  "IPUMS NHIS physical activity group: https://nhis.ipums.org/nhis-action/variables/group/behavior_pa"
)

manual <- c(
  "# Manual IPUMS NHIS Extract Request",
  "",
  paste0("Generated: ", stamp()),
  "",
  "Create the extract manually from IPUMS Health Surveys: NHIS, then place the downloaded data and metadata in `data/raw/`.",
  "",
  "## Samples",
  "",
  paste0("- ", samples, " (", sub("^ih", "", samples), " NHIS)"),
  "",
  "## Variables",
  "",
  paste0("- ", variables),
  "",
  "## Required metadata",
  "",
  "- DDI XML codebook",
  "- Basic codebook",
  "- Stata command file, if offered",
  "- Extract JSON/request metadata",
  "",
  "## After download",
  "",
  "```powershell",
  "Rscript code/r/pipeline/01_data_inventory.R",
  "Rscript code/r/pipeline/03_build_msa_survival_dataset.R",
  "Rscript code/r/pipeline/04_quality_checks.R",
  "```",
  "",
  "## Official documentation",
  "",
  paste0("- ", sources)
)
write_text(here("docs", "IPUMS_extract_request.md"), paste(manual, collapse = "\n"))

append_issue_once(
  "IPUMS extract requires manual confirmation",
  "The R/Stata-only repository writes the IPUMS extract payload and manual request instructions. Submit/download through IPUMS and place data plus metadata in `data/raw/` before building processed datasets."
)
message("Wrote IPUMS payload and manual extract instructions.")
