version 15
clear all
set more off

local project_root "."
capture confirm file "`project_root'/data/processed/msa_survival_full.dta"
if _rc {
    display as error "Could not find data/processed/msa_survival_full.dta. Run the Python build script first from the project root."
}

local full_data "`project_root'/data/processed/msa_survival_full.dta"
local log_file "`project_root'/outputs/logs/04_reviewer_cox_sensitivity.log"
local result_csv "`project_root'/outputs/tables/reviewer_cox_sensitivity.csv"
local report_md "`project_root'/outputs/tables/reviewer_cox_sensitivity.md"
local issue_file "`project_root'/outputs/logs/issues_to_resolve.md"
global issue_file "`issue_file'"

capture mkdir "`project_root'/outputs"
capture mkdir "`project_root'/outputs/logs"
capture mkdir "`project_root'/outputs/tables"
capture log close _all
log using "`log_file'", replace text

program define note_issue
    args message
    file open issue using "$issue_file", write append text
    file write issue _n "## " c(current_date) " " c(current_time) _n _n
    file write issue "`message'" _n
    file close issue
end

program define encode_if_needed
    syntax varname, Generate(name)
    capture confirm string variable `varlist'
    if !_rc {
        encode `varlist', gen(`generate')
    }
    else {
        clonevar `generate' = `varlist'
    }
end

program define add_encoded_covariates
    foreach v in sex race_ethnicity education poverty marital_status smoking_status alcohol_use bmi_cat self_rated_health aerobic_category {
        capture drop `v'_n
        encode_if_needed `v', generate(`v'_n)
    }
end

program define require_vars
    foreach v in age followup_time_years died_allcause weight_mortality msa_cat5 insufficient_msa year sex race_ethnicity education poverty marital_status smoking_status alcohol_use bmi_cat self_rated_health aerobic_category diabetes hypertension cvd_history cancer_history strata psu {
        capture confirm variable `v'
        if _rc {
            note_issue "Reviewer Cox sensitivity stopped: required variable `v' is missing."
            exit 111
        }
    }
end

program define prepare_sample
    syntax, MINAge(real) MAXAge(real) [OMITPoverty OMITBMI OMITAERobic EXCLUDE1997 LAG24 SEXValue(string) AGEBand(string)]

    require_vars
    keep if age >= `minage' & age <= `maxage'
    if "`exclude1997'" != "" {
        keep if year != 1997
    }
    if "`lag24'" != "" {
        keep if lag24_exclusion == 0
    }
    if "`sexvalue'" != "" {
        capture confirm string variable sex
        if !_rc {
            keep if sex == "`sexvalue'"
        }
        else {
            keep if sex == real("`sexvalue'")
        }
    }
    if "`ageband'" == "30_44" {
        keep if age >= 30 & age <= 44
    }
    if "`ageband'" == "45_54" {
        keep if age >= 45 & age <= 54
    }
    if "`ageband'" == "55_69" {
        keep if age >= 55 & age <= 69
    }

    local needed "age followup_time_years died_allcause weight_mortality insufficient_msa year sex race_ethnicity education marital_status smoking_status alcohol_use self_rated_health diabetes hypertension cvd_history cancer_history strata psu"
    if "`omitpoverty'" == "" local needed "`needed' poverty"
    if "`omitbmi'" == "" local needed "`needed' bmi_cat"
    if "`omitaerobic'" == "" local needed "`needed' aerobic_category"
    foreach v of local needed {
        drop if missing(`v')
    }

    add_encoded_covariates

    capture drop age_entry age_exit_all age_exit died_premature_30_69
    gen double age_entry = age
    gen double age_exit_all = age + followup_time_years
    gen byte died_premature_30_69 = died_allcause == 1 & age_exit_all < 70
    gen double age_exit = min(age_exit_all, 70)
    drop if missing(age_entry) | missing(age_exit) | age_exit <= age_entry

    stset age_exit [pweight=weight_mortality], enter(time age_entry) failure(died_premature_30_69)
end

program define fit_model
    args handle scenario model_label analysis_population design_type notes covars strata_terms use_svy

    local model_terms "ib0.insufficient_msa `covars'"
    local n_unweighted = _N
    quietly count if died_premature_30_69 == 1
    local n_fail_unweighted = r(N)

    if "`use_svy'" == "svy" {
        capture svyset psu [pweight=weight_mortality], strata(strata) singleunit(centered)
        if _rc {
            post `handle' ("`scenario'") ("`model_label'") ("`analysis_population'") ("`design_type'") ("1.insufficient_msa") (.) (.) (.) (.) (`n_unweighted') (`n_fail_unweighted') ("svyset failed") ("`notes'")
            note_issue "Reviewer Cox sensitivity svyset failed for `scenario' with Stata return code `_rc'."
            exit
        }
        capture noisily svy: stcox `model_terms', strata(`strata_terms')
    }
    else {
        capture noisily stcox `model_terms', vce(robust) strata(`strata_terms')
    }

    if _rc {
        post `handle' ("`scenario'") ("`model_label'") ("`analysis_population'") ("`design_type'") ("1.insufficient_msa") (.) (.) (.) (.) (`n_unweighted') (`n_fail_unweighted') ("model failed") ("`notes'")
        note_issue "Reviewer Cox sensitivity model failed: scenario=`scenario'; return code `_rc'."
    }
    else {
        scalar beta = _b[1.insufficient_msa]
        scalar se = _se[1.insufficient_msa]
        scalar hr = exp(beta)
        scalar ci_lower = exp(beta - invnormal(.975) * se)
        scalar ci_upper = exp(beta + invnormal(.975) * se)
        scalar p_value = 2 * normal(-abs(beta / se))
        post `handle' ("`scenario'") ("`model_label'") ("`analysis_population'") ("`design_type'") ("1.insufficient_msa") (hr) (ci_lower) (ci_upper) (p_value) (`n_unweighted') (`n_fail_unweighted') ("completed") ("`notes'")
    }
end

capture confirm file "`full_data'"
if _rc {
    note_issue "Reviewer Cox sensitivity stopped: full dataset not found at `full_data'."
    exit 601
}

tempfile reviewer_results
tempname result_handle
postfile `result_handle' str40 scenario str60 model_label str50 analysis_population str30 design_type str40 term double hazard_ratio ci_lower ci_upper p_value n_obs n_fail str20 status str160 notes using "`reviewer_results'", replace

local cov_full "i.race_ethnicity_n i.education_n i.poverty_n i.marital_status_n i.smoking_status_n i.alcohol_use_n i.bmi_cat_n i.self_rated_health_n i.aerobic_category_n i.diabetes i.hypertension i.cvd_history i.cancer_history"
local cov_no_poverty "i.race_ethnicity_n i.education_n i.marital_status_n i.smoking_status_n i.alcohol_use_n i.bmi_cat_n i.self_rated_health_n i.aerobic_category_n i.diabetes i.hypertension i.cvd_history i.cancer_history"

use "`full_data'", clear
prepare_sample, minage(18) maxage(120)
fit_model `result_handle' "adult_current" "Adult current covariates" "baseline adults 18+" "pweight robust" "Adult comparison; current covariates; age as time scale." "`cov_full'" "sex_n year" "robust"

use "`full_data'", clear
prepare_sample, minage(30) maxage(69)
fit_model `result_handle' "target_30_69_current" "Target 30-69 current covariates" "baseline adults 30-69, censored at 70" "pweight robust" "Primary target-population sensitivity; current covariates; age as time scale; premature mortality failure before age 70." "`cov_full'" "sex_n year" "robust"

use "`full_data'", clear
prepare_sample, minage(30) maxage(69) lag24
fit_model `result_handle' "target_30_69_lag24" "Target 30-69 lag 24 months" "baseline adults 30-69, censored at 70" "pweight robust" "Lagged target-population sensitivity; excludes deaths in first 24 months." "`cov_full'" "sex_n year" "robust"

use "`full_data'", clear
prepare_sample, minage(30) maxage(69) omitpoverty
fit_model `result_handle' "target_30_69_no_poverty" "Target 30-69 without PIR" "baseline adults 30-69, censored at 70" "pweight robust" "Reviewer missing-income sensitivity; omits poverty-income ratio." "`cov_no_poverty'" "sex_n year" "robust"

use "`full_data'", clear
prepare_sample, minage(30) maxage(69) exclude1997
fit_model `result_handle' "target_30_69_exclude_1997" "Target 30-69 excluding 1997" "baseline adults 30-69, censored at 70" "pweight robust" "Reviewer 1997 aerobic-activity sensitivity; excludes 1997 survey year." "`cov_full'" "sex_n year" "robust"

use "`full_data'", clear
prepare_sample, minage(30) maxage(69)
fit_model `result_handle' "target_30_69_svy" "Target 30-69 Taylor design SE" "baseline adults 30-69, censored at 70" "svy Taylor linearized" "Uses svyset PSU/STRATA with mortality weights; point estimate retained only if svy: stcox succeeds." "`cov_full'" "sex_n year" "svy"

use "`full_data'", clear
prepare_sample, minage(30) maxage(69) sexvalue("Female")
fit_model `result_handle' "target_30_69_female" "Target 30-69 women" "baseline women 30-69, censored at 70" "pweight robust" "Sex-specific target-population sensitivity." "`cov_full'" "year" "robust"

use "`full_data'", clear
prepare_sample, minage(30) maxage(69) sexvalue("Male")
fit_model `result_handle' "target_30_69_male" "Target 30-69 men" "baseline men 30-69, censored at 70" "pweight robust" "Sex-specific target-population sensitivity." "`cov_full'" "year" "robust"

use "`full_data'", clear
prepare_sample, minage(30) maxage(69) ageband("30_44")
fit_model `result_handle' "target_30_69_age_30_44" "Target ages 30-44" "baseline adults 30-44, censored at 70" "pweight robust" "Age-band sensitivity; baseline ages 30-44." "`cov_full'" "sex_n year" "robust"

use "`full_data'", clear
prepare_sample, minage(30) maxage(69) ageband("45_54")
fit_model `result_handle' "target_30_69_age_45_54" "Target ages 45-54" "baseline adults 45-54, censored at 70" "pweight robust" "Age-band sensitivity; baseline ages 45-54." "`cov_full'" "sex_n year" "robust"

use "`full_data'", clear
prepare_sample, minage(30) maxage(69) ageband("55_69")
fit_model `result_handle' "target_30_69_age_55_69" "Target ages 55-69" "baseline adults 55-69, censored at 70" "pweight robust" "Age-band sensitivity; baseline ages 55-69." "`cov_full'" "sex_n year" "robust"

postclose `result_handle'

use "`reviewer_results'", clear
export delimited using "`result_csv'", replace

local run_date "`c(current_date)'"
local run_time "`c(current_time)'"
file open rep using "`report_md'", write replace text
file write rep "# Reviewer Cox Sensitivity Models" _n _n
file write rep "Generated by code/stata/04_reviewer_cox_sensitivity.do on `run_date' `run_time'." _n _n
file write rep "The primary reviewer-response contrast estimates the insufficient-MSA hazard ratio among baseline adults aged 30--69 years, with attained age as the time scale and censoring at age 70 so that the HR aligns with the premature mortality burden target." _n _n
file write rep "| Scenario | Model | Design | n | events | HR | 95% CI | p | Status |" _n
file write rep "|---|---|---|---:|---:|---:|---:|---:|---|" _n
quietly count
local nrows = r(N)
forvalues i = 1/`nrows' {
    local scenario_i = scenario[`i']
    local model_i = model_label[`i']
    local design_i = design_type[`i']
    local status_i = status[`i']
    local n_i : display %12.0fc n_obs[`i']
    local fail_i : display %12.0fc n_fail[`i']
    if missing(hazard_ratio[`i']) {
        file write rep "| `scenario_i' | `model_i' | `design_i' | `n_i' | `fail_i' | . | . | . | `status_i' |" _n
    }
    else {
        local hr_i : display %5.3f hazard_ratio[`i']
        local lo_i : display %5.3f ci_lower[`i']
        local hi_i : display %5.3f ci_upper[`i']
        local p_i : display %6.4f p_value[`i']
        file write rep "| `scenario_i' | `model_i' | `design_i' | `n_i' | `fail_i' | `hr_i' | `lo_i'--`hi_i' | `p_i' | `status_i' |" _n
    }
}
file write rep _n "Notes: target models use premature mortality failure before age 70. The no-PIR model addresses income missingness. The 1997-exclusion model addresses the reviewer concern about the 1997 aerobic physical-activity assessment. The svy model uses svyset psu [pweight=weight_mortality], strata(strata) singleunit(centered) when supported by Stata." _n
file close rep

display as text _n "Reviewer Cox sensitivity complete."
display as text "Wrote `result_csv'"
display as text "Wrote `report_md'"
log close
