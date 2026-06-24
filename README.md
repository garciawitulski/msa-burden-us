# MSA burden US

This repository contains the R and Stata workflow for estimating the premature
mortality and productivity burden potentially attributable to insufficient
muscle-strengthening activity (MSA) among US adults.

Raw, processed, and generated data are not versioned. The workflow documents how
to obtain the required NHIS, mortality, life-table, and productivity inputs, then
writes derived logs, tables, and figures under `outputs/`.

## Code Layout

- `code/stata/`: NHIS-LMF survival checks and Cox models.
- `code/r/pipeline/`: data preparation, PAFs, burden calculations, validation,
  manuscript tables, and supplement tables.
- `code/r/figures/`: manuscript and supplement figure rendering.
- `code/r/lib/msaburden.R`: shared R helpers.

The public workflow uses only R and Stata code.

## Data Inputs

Primary survival source:

- IPUMS Health Surveys: NHIS linked to NCHS Linked Mortality Files.
- Planned samples: NHIS 1997-2018.
- Manual extract instructions are written to `docs/IPUMS_extract_request.md`.

Current exposure prevalence source:

- NHIS 2024 Sample Adult public-use file from CDC/NCHS.
- The download helper writes files under `data/raw/nhis_2024/`.

External burden inputs:

- CDC WONDER final all-cause mortality by age group and sex.
- NCHS United States Life Tables.
- ACS PUMS productivity inputs when productivity losses are reported.

The R scripts create templates/manual instructions when external inputs are
missing. They do not fabricate source data.

## Software

Required:

- Stata 15 or newer for Cox models.
- R for all non-Stata workflow steps.

Recommended R packages:

- `haven` or `foreign` for writing Stata `.dta` files.
- `jsonlite`, `httr`, `readxl`, and `xml2` are optional helpers for external
  input handling.

## Run Order

From the repository root:

```powershell
Rscript code/r/pipeline/00_setup_project.R
Rscript code/r/pipeline/01_data_inventory.R
Rscript code/r/pipeline/02_download_or_prepare_ipums_extract.R
```

After placing the IPUMS NHIS-LMF extract and metadata in `data/raw/`:

```powershell
Rscript code/r/pipeline/03_build_msa_survival_dataset.R
Rscript code/r/pipeline/04_quality_checks.R
```

Optional Stata checks and preliminary models:

```stata
do code/stata/01_check_survival_dataset.do
do code/stata/02_preliminary_cox_models.do
```

Refined survival models:

```stata
do code/stata/03_refined_cox_models.do
do code/stata/04_reviewer_cox_sensitivity.do
```

NHIS 2024 prevalence and burden pipeline:

```powershell
Rscript code/r/pipeline/07_download_nhis_2024_prevalence.R
Rscript code/r/pipeline/08_build_nhis_2024_msa_prevalence.R
Rscript code/r/pipeline/19_make_reviewer_revision_summaries.R
Rscript code/r/pipeline/06_burden_paf_deaths_yll.R
Rscript code/r/pipeline/09_download_or_prepare_external_mortality_lifetable.R
Rscript code/r/pipeline/10_compute_attributable_deaths_yll.R
Rscript code/r/pipeline/11_validate_burden_outputs.R
Rscript code/r/pipeline/16_compute_attributable_deaths_yll_premature_30_69.R
Rscript code/r/pipeline/13_compute_life_expectancy_gain.R
Rscript code/r/pipeline/14_compute_productivity_losses.R
Rscript code/r/pipeline/17_validate_premature_30_69_outputs.R
Rscript code/r/pipeline/12_make_manuscript_tables.R
Rscript code/r/pipeline/20_make_supplement_appendix_tables.R
Rscript code/r/pipeline/derive_subtotals.R
Rscript code/r/figures/render_all.R
```

The non-Stata R steps can also be run in sequence with:

```powershell
Rscript code/r/pipeline/run_all.R
```

For the PCD resubmission figure upload package:

```powershell
Rscript code/r/figures/render_pcd_submission_figures.R
```

## Main Outputs

- `data/processed/msa_survival_full.csv`
- `data/processed/msa_survival_main_completecase.csv`
- `data/processed/msa_survival_lag24_completecase.csv`
- `outputs/tables/hr_inputs_for_burden.csv`
- `outputs/tables/msa_paf_insufficient_premature_30_69_nhis2024.csv`
- `outputs/tables/msa_attributable_deaths_premature_30_69_nhis2024.csv`
- `outputs/tables/msa_yll_premature_30_69_nhis2024.csv`
- `outputs/tables/msa_life_expectancy_gain_premature_30_69_nhis2024.csv`
- `outputs/tables/msa_productivity_losses_premature_30_69_nhis2024.csv`
- `outputs/tables/manuscript/`
- `outputs/figures/manuscript/`

## Interpretation

The burden estimates are comparative-risk estimates under a modelled
counterfactual in which adults meet the MSA guideline. They should be described
as potentially attributable to insufficient MSA, not as proof that insufficient
MSA caused each death or that the counterfactual would directly produce cost
savings.

## Known Limitations

- The public-use IPUMS NHIS mortality extract may not include exact
  person-month follow-up. If unavailable, the R build script constructs a
  quarter-based approximation from survey year/quarter and death year/quarter.
- NHIS 2024 is used for contemporary exposure prevalence only; it is not used to
  estimate mortality hazard ratios.
- External mortality, life-table, and productivity inputs must be official and
  documented before downstream burden outputs are interpreted.
