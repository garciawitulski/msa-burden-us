# MSA burden US

This repository currently contains the Stata, R, and Python workflow for
estimating the premature mortality and productivity burden potentially
attributable to insufficient muscle-strengthening activity (MSA) among US
adults.

Raw and processed data are not versioned. The scripts document how to obtain or
prepare the required NHIS, mortality, life-table, and productivity inputs, and
write generated tables, logs, and figures under `outputs/`.

## Code Layout and R/Stata Target

The active model and figure layer is intentionally limited to Stata and R:

- `code/stata/`: NHIS-LMF survival checks and Cox models.
- `code/r/figures/`: manuscript and supplement figure rendering.
- `code/python/`: retained for now because it is still the current source for
  data preparation, burden calculations, external-input handling, validation,
  and manuscript table formatting.

Legacy R figure scripts, standalone Python figure helpers, and the Python Cox
fallback have been removed. To make the repository fully R/Stata-only without
losing reproducibility, the remaining `code/python/` steps should be ported to R
before that directory is deleted.

## Research Objective

The broader study will estimate the mortality and economic burden attributable
to insufficient MSA among US adults. Later stages will use dose-response
estimates to compute attributable mortality, life expectancy gains, years of
life lost, and productivity losses.

The workflow builds individual-level NHIS-LMF survival datasets, estimates Cox
models, computes population attributable fractions and burden estimates, and
renders manuscript figures.

## Data Source

Preferred source: IPUMS Health Surveys: NHIS linked to NCHS Linked Mortality
Files (LMF).

Planned survey years: 1997-2018. This range is based on the joint availability
of adult strengthening activity variables, adult physical activity covariates,
and public-use mortality linkage through the 2019 LMF update. The 1997 aerobic
activity variables need special review because some are available only for
quarters 3-4.

Important documentation:

- IPUMS API microdata docs: https://developer.ipums.org/docs/v2/apiprogram/apis/microdata/
- IPUMS API extract workflow: https://developer.ipums.org/docs/v2/workflows/create_extracts/microdata/
- IPUMS NHIS sample IDs: https://nhis.ipums.org/nhis-action/samples/sample_ids
- IPUMS NHIS mortality variables: https://nhis.ipums.org/nhis-action/variables/group/mortality_mortality
- IPUMS NHIS physical activity variables: https://nhis.ipums.org/nhis-action/variables/group/behavior_pa
- NCHS public-use LMF description: https://nhis.ipums.org/nhis/resources/public-use-linked-mortality-file-description.pdf

## How to Obtain Data

From the project root, run:

```powershell
python code/python/00_setup_project.py
python code/python/02_download_or_prepare_ipums_extract.py
```

The script first checks `IPUMS_API_KEY`.

If `IPUMS_API_KEY` is set, it writes the extract payload to
`data/raw/ipums_nhis_extract_payload.json`, submits the IPUMS NHIS extract, polls
for completion, and downloads the returned data and metadata files into
`data/raw/`.

If the IPUMS API rejects the request or a download fails, the script records the
exact sanitized API error in `outputs/logs/issues_to_resolve.md`. It does not
print, write, or otherwise persist the API key.

If `IPUMS_API_KEY` is not set, it writes
`docs/IPUMS_extract_request.md` with the manual extract instructions. No data are
fabricated.

Always keep the DDI XML, basic codebook, Stata command file, and extract
metadata with the raw data. The build script checks metadata before cleaning and
stops if required variables cannot be verified.

## Run Order

```powershell
python code/python/00_setup_project.py
python code/python/01_data_inventory.py
python code/python/02_download_or_prepare_ipums_extract.py
python code/python/01_data_inventory.py
python code/python/03_build_msa_survival_dataset.py
python code/python/04_quality_checks.py
```

Optional Stata check after processed data exist:

```stata
do code/stata/01_check_survival_dataset.do
```

Preliminary dose-response Cox models, after processed data are built:

```stata
do code/stata/02_preliminary_cox_models.do
```

Refined age-as-time-scale Cox models, before any burden calculations:

```stata
do code/stata/03_refined_cox_models.do
```

## Processed Outputs

The build and quality scripts create these files in `data/processed/` when raw
data and metadata are available:

- `msa_survival_full.csv` and `msa_survival_full.dta`: cleaned adult survival
  dataset with mortality outcomes, MSA exposure, aerobic activity, covariates,
  weights, design variables, and missingness flags.
- `msa_survival_main_completecase.csv` and `.dta`: complete-case dataset for the
  main dose-response Cox models.
- `msa_survival_lag24_completecase.csv` and `.dta`: complete-case dataset
  excluding deaths in the first 24 months.
- `msa_variable_dictionary.csv`: constructed variable dictionary.
- `msa_sample_flow.csv`: sample size after each exclusion.
- `msa_descriptive_summary.csv`: weighted and unweighted summary statistics.

Additional logs/tables are written under `outputs/logs/` and `outputs/tables/`.
`outputs/logs/variable_availability_report.md` records the exact IPUMS source
variables, labels, codings, years available, missingness, usability, and
concerns checked before dataset construction.
If a required variable cannot be found or interpreted, the scripts write
`outputs/logs/issues_to_resolve.md` and stop.

## Key Constructed Variables

Main exposure:

- `msa_days_week`: weekly MSA frequency from `STRONGFWK`. IPUMS labels
  `STRONGFWK` as times per week, so this is a days/week proxy rather than a
  verified count of distinct days.
- `msa_cat5`: 0, 1, 2, 3-4, and 5+ days/times per week; less-than-weekly
  activity is grouped with 0 days/week for this requested five-category
  exposure.
- `msa_guideline`: 1 if MSA frequency is at least 2 times per week.
- `insufficient_msa`: 1 if MSA frequency is below 2 times per week.

Aerobic activity:

- `aerobic_minutes_meq_weekly`: moderate minutes plus 2 times vigorous minutes.
- `aerobic_guideline_cat`: inactive, insufficiently active, meets guideline.
- `aerobic_meets_guideline`: 1 if at least 150 moderate-equivalent minutes/week.
- `combined_guideline`: neither guideline, MSA only, aerobic only, both.

Outcomes:

- Main outcome: `died_allcause`.
- Secondary outcomes if public-use data support them: `died_cvd` and
  `died_cancer`.

## Methodological Notes for Later Models

Final dose-response models will likely use Cox proportional hazards models.
The main exposure will preserve MSA frequency categories. The key contrast will
be insufficient MSA versus meeting the guideline, but dose-response categories
should remain available.

Models should adjust for aerobic physical activity to isolate the MSA
association from general physical activity. Sensitivity analyses should exclude
deaths in the first 24 months and compare models with and without baseline
chronic disease covariates.

## Preliminary Dose-response Survival Models

`code/stata/02_preliminary_cox_models.do` estimates preliminary sequential Cox
models for all-cause mortality using `msa_survival_main_completecase.dta`, then
repeats the fully adjusted model in `msa_survival_lag24_completecase.dta`.
Outputs are designed to be written to `outputs/tables/` as preliminary hazard
ratio CSVs and plot-ready dose-response data. The scripts do not compute PAFs,
attributable deaths, years of life lost, life expectancy, or economic costs.

## Refined Survival Models

`code/stata/03_refined_cox_models.do` refines the Cox analysis before any burden
calculation by using age as the analysis time. It creates `age_entry` and
`age_exit` in memory only, then fits all-cause mortality models for three MSA
specifications: original five-category frequency, an optimal-range contrast
with 2-4 times/week as the reference, and insufficient MSA versus meeting the
guideline.

The refined script also estimates models stratified by sex, survey year, and
both sex and survey year, repeats selected models in the lag-24 dataset, runs
proportional-hazards diagnostics when Stata permits, and writes outputs to
`outputs/tables/refined_cox_msa_allcause.csv`,
`outputs/tables/refined_cox_ph_diagnostics.csv`, and
`outputs/tables/refined_cox_interpretation.md`. It does not compute PAFs,
attributable deaths, YLL, life expectancy, or costs.

## Burden Calculation Pipeline

`code/python/06_burden_paf_deaths_yll.py` is the first burden-calculation
pipeline. It uses the refined insufficient-MSA Cox contrast as the primary
relative-risk input and estimates weighted prevalence with
`weight_sample_adult` (`SAMPWEIGHT`), not the mortality weight. It writes:

- `outputs/tables/msa_prevalence_insufficient.csv`
- `outputs/tables/msa_paf_insufficient.csv`
- `outputs/tables/msa_paf_insufficient_montecarlo.csv`
- `outputs/tables/msa_prevalence_insufficient_by_period.csv`
- `outputs/tables/msa_paf_insufficient_by_period.csv`
- `outputs/tables/msa_paf_insufficient_montecarlo_by_period.csv`
- `outputs/tables/burden_readiness_report.md`

Run it from the project root:

```powershell
python code/python/06_burden_paf_deaths_yll.py
```

The script treats burden estimates as preliminary comparative-risk estimates
under a modelled counterfactual, not as proof that insufficient MSA causes
deaths. It uses Monte Carlo simulation for HR uncertainty and currently treats
prevalence as fixed.

The preferred present-day prevalence period is NHIS 2024 when the 2024
processed prevalence dataset is available. The recent pooled 2015-2018 estimate,
latest-year 2018 estimate, and full pooled 1997-2018 estimate are retained as
sensitivity or historical analyses. For the main manuscript burden analysis,
the pipeline also creates a premature mortality scenario restricted to ages
30-69.

The script only computes attributable deaths and YLL if official external
inputs are present in `data/external/`. If they are missing, it creates input
templates and documentation instead of fabricating data:

- `data/external/us_allcause_deaths_template.csv`
- `data/external/us_life_table_template.csv`
- `data/external/us_productivity_inputs_template.csv`
- `docs/external_mortality_data_needed.md`
- `docs/external_life_table_data_needed.md`
- `docs/external_productivity_data_needed.md`

Life expectancy and productivity modules are separate downstream scripts. YLL is
only computed when documented death counts and remaining life expectancy inputs
are available.

## NHIS 2024 Current Prevalence

NHIS 2024 is used only for contemporary exposure prevalence. It is not used to
estimate mortality hazard ratios because it does not yet have sufficient linked
mortality follow-up. The hazard ratios remain based on the NHIS-LMF 1997-2018
survival models.

Run order:

```powershell
python code/python/07_download_nhis_2024_prevalence.py
python code/python/08_build_nhis_2024_msa_prevalence.py
python code/python/06_burden_paf_deaths_yll.py
```

`code/python/07_download_nhis_2024_prevalence.py` first attempts to use the
IPUMS NHIS API without printing or saving the API key. In the current run, the
IPUMS request failed because `RACEA` was not available in the selected 2024
sample, so the script used the official CDC/NCHS 2024 Sample Adult public-use
CSV and codebook instead.

`code/python/08_build_nhis_2024_msa_prevalence.py` reads the downloaded 2024
Sample Adult file, maps CDC `STRFREQW_A` to `msa_times_week_2024`, uses
`WTFA_A` as the sample adult survey weight, and creates:

- `msa_guideline_2024`
- `insufficient_msa_2024`
- age group, sex, race/ethnicity, education, poverty, and region categories
- optional combined aerobic/strength guideline information from `PA18_05R_A`

The processed 2024 outputs are:

- `data/processed/nhis_2024/nhis_2024_msa_prevalence_dataset.csv`
- `data/processed/nhis_2024/nhis_2024_msa_prevalence_dataset.dta`
- `outputs/tables/nhis_2024_msa_prevalence_overall.csv`
- `outputs/tables/nhis_2024_msa_prevalence_by_sex.csv`
- `outputs/tables/nhis_2024_msa_prevalence_by_age.csv`
- `outputs/tables/nhis_2024_msa_prevalence_by_age_sex.csv`
- `outputs/tables/nhis_2024_msa_prevalence_by_sociodemographics.csv`

When the 2024 processed dataset is present, the burden script uses
`nhis_2024_current` as the preferred present-day prevalence scenario and writes:

- `outputs/tables/msa_paf_insufficient_using_nhis2024.csv`
- `outputs/tables/msa_paf_insufficient_montecarlo_using_nhis2024.csv`
- `outputs/tables/msa_paf_insufficient_premature_30_69_nhis2024.csv`
- `outputs/tables/msa_paf_insufficient_montecarlo_premature_30_69_nhis2024.csv`

For premature mortality, `08_build_nhis_2024_msa_prevalence.py` additionally
uses exact age groups 30-34, 35-44, 45-54, 55-64, and 65-69 and writes:

- `outputs/tables/nhis_2024_msa_prevalence_premature_30_69_overall.csv`
- `outputs/tables/nhis_2024_msa_prevalence_premature_30_69_by_sex.csv`
- `outputs/tables/nhis_2024_msa_prevalence_premature_30_69_by_age.csv`
- `outputs/tables/nhis_2024_msa_prevalence_premature_30_69_by_age_sex.csv`

## Premature Mortality 30-69 Main Analysis

The main manuscript burden analysis now focuses on deaths occurring between
ages 30 and 69 years, following the WHO-style premature mortality range. The
main exposure is `insufficient_msa` (<2 times/week), and the counterfactual is
that adults aged 30-69 meet the MSA guideline.

The main HR input is the reviewer-response target-population Cox estimate for
baseline adults aged 30-69 years, censored at age 70, with NHIS design variables
used for Taylor-linearized standard errors. Existing adult refined HRs are
retained only as comparison sensitivities. The HR inputs are stored in:

- `outputs/tables/hr_inputs_for_burden.csv`

Final run order for the premature 30-69 pipeline:

```powershell
StataMP-64.exe /e do code/stata/04_reviewer_cox_sensitivity.do
python code/python/19_make_reviewer_revision_summaries.py
python code/python/08_build_nhis_2024_msa_prevalence.py
python code/python/06_burden_paf_deaths_yll.py
python code/python/16_compute_attributable_deaths_yll_premature_30_69.py
python code/python/13_compute_life_expectancy_gain.py
python code/python/14_compute_productivity_losses.py
python code/python/17_validate_premature_30_69_outputs.py
python code/python/12_make_manuscript_tables_figures.py
Rscript code/r/figures/render_all.R
```

For the PCD resubmission figure upload package, run the R figure-export helper
from the project root after the manuscript figures are current:

```powershell
Rscript code/r/figures/render_pcd_submission_figures.R
```

It writes separate native/vector and PDF files under
`submission_pcd/figures/`, with a ScholarOne upload manifest in
`submission_pcd/figures/FIGURE_FILES_FOR_PCD.txt`.

Main premature outputs:

- `data/external/us_allcause_deaths_by_age_sex_premature_30_69.csv`
- `outputs/tables/msa_attributable_deaths_premature_30_69_nhis2024.csv`
- `outputs/tables/msa_yll_premature_30_69_nhis2024.csv`
- `outputs/tables/msa_burden_summary_premature_30_69_nhis2024.csv`
- `outputs/tables/msa_life_expectancy_gain_premature_30_69_nhis2024.csv`
- `outputs/tables/msa_life_expectancy_gain_report_premature_30_69.md`
- `outputs/tables/msa_productivity_losses_premature_30_69_nhis2024.csv`
- `outputs/tables/msa_productivity_losses_report_premature_30_69.md`
- `outputs/tables/msa_burden_validation_report_premature_30_69.md`
- `outputs/tables/reviewer_cox_sensitivity.csv`
- `outputs/tables/reviewer_missingness_impact.csv`

The current validated main premature results use NHIS 2024 prevalence, CDC
WONDER final 2024 all-cause mortality, NCHS United States Life Tables 2023, and
ACS PUMS 2024 productivity inputs. They should be described as potentially
attributable under the modelled counterfactual, not as direct causal estimates.
Previous all-adult 18+ burden outputs remain available as
supplementary analyses.

## Known Limitations

- The public-use IPUMS NHIS mortality extract may not include exact person-month
  follow-up. If exact follow-up is unavailable, the current script constructs a
  quarter-based approximation from survey year/quarter and death year/quarter and
  records this in the issue log.
- The downloaded 2019 LMF variables provide public-use mortality follow-up
  through December 31, 2019, not through 2022.
- Cause-specific mortality is limited by public-use LMF detail.
- The 1997 physical activity coverage sensitivity is retained because one
  reviewer questioned whether the first included NHIS year affects the HR.
- The cleaning code preserves missing covariates in the full dataset and creates
  a separate complete-case dataset; it does not impute missing covariates.

## Next Steps

1. Obtain the IPUMS NHIS extract and metadata.
2. Run the build and quality-check scripts.
3. Review `outputs/logs/issues_to_resolve.md`,
   `outputs/tables/msa_year_inclusion.csv`, and
   `data/processed/msa_variable_dictionary.csv`.
4. Only after the analytic datasets are verified, write the Cox model scripts.

<!-- BEGIN EXTERNAL_MORTALITY_YLL -->
## External Mortality and YLL Inputs

Run after the NHIS 2024 prevalence PAF pipeline:

```powershell
StataMP-64.exe /e do code/stata/04_reviewer_cox_sensitivity.do
python code/python/19_make_reviewer_revision_summaries.py
python code/python/09_download_or_prepare_external_mortality_lifetable.py
python code/python/10_compute_attributable_deaths_yll.py
python code/python/11_validate_burden_outputs.py
python code/python/16_compute_attributable_deaths_yll_premature_30_69.py
python code/python/13_compute_life_expectancy_gain.py
python code/python/14_compute_productivity_losses.py
python code/python/17_validate_premature_30_69_outputs.py
python code/python/12_make_manuscript_tables_figures.py
Rscript code/r/figures/render_all.R
```

`09_download_or_prepare_external_mortality_lifetable.py` prepares official
external inputs from CDC WONDER final all-cause mortality and NCHS United States
Life Tables. `10_compute_attributable_deaths_yll.py` links those inputs to the
NHIS 2024 age-sex PAFs and computes potentially attributable deaths and YLL.
`11_validate_burden_outputs.py` reconciles overall-PAF and age-sex-specific PAF
burden totals and creates validation tables before productivity-cost work.
`16_compute_attributable_deaths_yll_premature_30_69.py` computes the main
premature mortality burden using exact 30-69 age groups from CDC WONDER final
2024 mortality. `13_compute_life_expectancy_gain.py` adds approximate
temporary-life-expectancy 30-70 estimates for the premature scenario.
`14_compute_productivity_losses.py` prepares ACS PUMS 2024 economic inputs and
computes human-capital productivity losses for premature deaths aged 30-69 when
the ACS API is available; otherwise it creates manual instructions without
fabricating costs.
`12_make_manuscript_tables_figures.py` formats the validated survival and burden
outputs into manuscript-ready tables under `outputs/tables/manuscript/`. Figures
are rendered from the active R scripts with
`Rscript code/r/figures/render_all.R`.
<!-- END EXTERNAL_MORTALITY_YLL -->
