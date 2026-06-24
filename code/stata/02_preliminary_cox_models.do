version 15
clear all
set more off

local project_root "."
local log_file "`project_root'/outputs/logs/02_preliminary_cox_models.log"
local issue_file "`project_root'/outputs/logs/issues_to_resolve.md"
local main_data "`project_root'/data/processed/msa_survival_main_completecase.dta"
local lag_data "`project_root'/data/processed/msa_survival_lag24_completecase.dta"
local main_output "`project_root'/outputs/tables/cox_msa_allcause_preliminary.csv"
local lag_output "`project_root'/outputs/tables/cox_msa_allcause_lag24_preliminary.csv"
local plot_output "`project_root'/outputs/tables/msa_dose_response_plot_data.csv"
global issue_file "`issue_file'"

capture log close _all
capture mkdir "`project_root'/outputs"
capture mkdir "`project_root'/outputs/logs"
capture mkdir "`project_root'/outputs/tables"

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

program define make_analysis_aliases
    capture confirm variable aerobic_guideline
    if _rc {
        capture confirm variable aerobic_meets_guideline
        if !_rc clonevar aerobic_guideline = aerobic_meets_guideline
    }

    capture confirm variable combined_pa_guideline
    if _rc {
        capture confirm variable combined_guideline
        if !_rc clonevar combined_pa_guideline = combined_guideline
    }

    capture confirm variable age_group
    if _rc {
        capture confirm variable age_cat
        if !_rc clonevar age_group = age_cat
    }
end

program define prepare_covariates
    make_analysis_aliases
    foreach v in sex race_ethnicity education poverty marital_status bmi_cat smoking_status alcohol_use self_rated_health aerobic_category age_group combined_pa_guideline {
        capture confirm variable `v'
        if !_rc {
            capture drop `v'_n
            encode_if_needed `v', generate(`v'_n)
        }
    }
end

program define required_checks
    foreach v in followup_time_years died_allcause weight_mortality msa_cat5 msa_guideline insufficient_msa age sex year {
        capture confirm variable `v'
        if _rc {
            note_issue "Preliminary Cox models stopped: required variable `v' is missing."
            exit 111
        }
    }
end

program define post_coefficients
    args handle dataset_name model_name
    local coef_list : colnames e(b)
    foreach coef of local coef_list {
        if "`coef'" != "_cons" {
            scalar beta = _b[`coef']
            scalar se = _se[`coef']
            scalar hr = exp(beta)
            scalar ci_lower = exp(beta - invnormal(.975) * se)
            scalar ci_upper = exp(beta + invnormal(.975) * se)
            scalar p_value = 2 * normal(-abs(beta / se))
            post `handle' ("`dataset_name'") ("`model_name'") ("`coef'") (hr) (ci_lower) (ci_upper) (p_value)
        }
    }
end

program define fit_and_post
    args handle dataset_name model_name model_terms
    display as text _n "Fitting `dataset_name' `model_name'"
    capture noisily stcox `model_terms', vce(robust)
    if _rc {
        note_issue "Preliminary Cox model problem: `dataset_name' `model_name' failed with Stata return code `_rc'."
    }
    else {
        post_coefficients `handle' "`dataset_name'" "`model_name'"
    }
end

capture confirm file "`main_data'"
if _rc {
    note_issue "Preliminary Cox models stopped: `main_data' was not found."
    exit 601
}
capture confirm file "`lag_data'"
if _rc {
    note_issue "Preliminary Cox lag-24 model skipped: `lag_data' was not found."
}

use "`main_data'", clear
required_checks
prepare_covariates

describe
summarize followup_time_years died_allcause weight_mortality
tab msa_cat5, missing
tab msa_guideline, missing
capture tab aerobic_guideline, missing
capture tab combined_pa_guideline, missing
tab year, missing
tab sex, missing
capture tab age_group, missing

stset followup_time_years [pweight=weight_mortality], failure(died_allcause)

tempfile main_results lag_results plot_results
tempname main_handle lag_handle plot_handle
postfile `main_handle' str20 dataset str40 model_name str80 term double hazard_ratio ci_lower ci_upper p_value using "`main_results'", replace
postfile `lag_handle' str20 dataset str40 model_name str80 term double hazard_ratio ci_lower ci_upper p_value using "`lag_results'", replace

local m1 "ib0.msa_cat5 c.age i.sex_n i.year"
local m2 "`m1' i.race_ethnicity_n i.education_n i.poverty_n i.marital_status_n"
local m3 "`m2' i.smoking_status_n i.alcohol_use_n i.bmi_cat_n i.self_rated_health_n"
local m4 "`m3' i.aerobic_category_n"
local m5 "`m4' i.diabetes i.hypertension i.cvd_history i.cancer_history"
local guideline "ib0.insufficient_msa c.age i.sex_n i.year i.race_ethnicity_n i.education_n i.poverty_n i.marital_status_n i.smoking_status_n i.alcohol_use_n i.bmi_cat_n i.self_rated_health_n i.aerobic_category_n i.diabetes i.hypertension i.cvd_history i.cancer_history"

fit_and_post `main_handle' "main" "Model 1" "`m1'"
fit_and_post `main_handle' "main" "Model 2" "`m2'"
fit_and_post `main_handle' "main" "Model 3" "`m3'"
fit_and_post `main_handle' "main" "Model 4" "`m4'"
fit_and_post `main_handle' "main" "Model 5" "`m5'"
fit_and_post `main_handle' "main" "Guideline model" "`guideline'"

capture noisily stcox `m5', vce(robust)
if !_rc {
    capture noisily estat phtest, detail
    if _rc {
        note_issue "Proportional hazards diagnostic could not be completed after the main fully adjusted model; Stata return code `_rc'."
    }
}

postclose `main_handle'

if "`lag_data'" != "" {
    capture confirm file "`lag_data'"
    if !_rc {
        use "`lag_data'", clear
        required_checks
        prepare_covariates
        stset followup_time_years [pweight=weight_mortality], failure(died_allcause)
        fit_and_post `lag_handle' "lag24" "Model 5 lag24" "`m5'"
    }
}
postclose `lag_handle'

use "`main_results'", clear
export delimited using "`main_output'", replace

use "`lag_results'", clear
export delimited using "`lag_output'", replace

use "`main_results'", clear
append using "`lag_results'"
keep if strpos(term, ".msa_cat5") > 0
gen msa_category = ""
replace msa_category = "1 day/week" if strpos(term, "1.msa_cat5") > 0
replace msa_category = "2 days/week" if strpos(term, "2.msa_cat5") > 0
replace msa_category = "3-4 days/week" if strpos(term, "3.msa_cat5") > 0
replace msa_category = "5+ days/week" if strpos(term, "4.msa_cat5") > 0
keep msa_category hazard_ratio ci_lower ci_upper model_name
export delimited using "`plot_output'", replace

display as text _n "Preliminary Cox models complete. No attributable burden, life expectancy, or cost estimates computed."
log close
