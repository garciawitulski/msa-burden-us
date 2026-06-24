version 15
clear all
set more off

local project_root "."
capture confirm file "`project_root'/data/processed/msa_survival_main_completecase.dta"
if _rc {
    display as error "Could not find data/processed/msa_survival_main_completecase.dta. Run the Python build script first from the project root."
}

local main_data "`project_root'/data/processed/msa_survival_main_completecase.dta"
local lag_data "`project_root'/data/processed/msa_survival_lag24_completecase.dta"
local log_file "`project_root'/outputs/logs/03_refined_cox_models.log"
local issue_file "`project_root'/outputs/logs/issues_to_resolve.md"
local result_csv "`project_root'/outputs/tables/refined_cox_msa_allcause.csv"
local ph_csv "`project_root'/outputs/tables/refined_cox_ph_diagnostics.csv"
local report_md "`project_root'/outputs/tables/refined_cox_interpretation.md"
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

program define required_checks
    foreach v in age followup_time_years died_allcause weight_mortality msa_cat5 insufficient_msa year sex race_ethnicity education poverty marital_status smoking_status alcohol_use bmi_cat self_rated_health aerobic_category diabetes hypertension cvd_history cancer_history {
        capture confirm variable `v'
        if _rc {
            note_issue "Refined Cox models stopped: required variable `v' is missing."
            exit 111
        }
    }
end

program define prepare_refined_data
    required_checks

    capture drop age_entry age_exit
    gen double age_entry = age
    gen double age_exit = age + followup_time_years
    count if missing(age_entry) | missing(age_exit) | age_exit <= age_entry
    if r(N) > 0 {
        note_issue "Refined Cox models found observations with missing or non-positive age-time follow-up. These observations are dropped in memory only."
        drop if missing(age_entry) | missing(age_exit) | age_exit <= age_entry
    }

    capture drop msa_optimal_cat
    gen byte msa_optimal_cat = .
    replace msa_optimal_cat = 0 if inlist(msa_cat5, 0, 1)
    replace msa_optimal_cat = 1 if inlist(msa_cat5, 2, 3)
    replace msa_optimal_cat = 2 if msa_cat5 == 4
    label define msa_optimal_cat 0 "0-1 times/week" 1 "2-4 times/week" 2 "5+ times/week", replace
    label values msa_optimal_cat msa_optimal_cat

    foreach v in sex race_ethnicity education poverty marital_status smoking_status alcohol_use bmi_cat self_rated_health aerobic_category {
        capture drop `v'_n
        encode_if_needed `v', generate(`v'_n)
    }

    stset age_exit [pweight=weight_mortality], enter(time age_entry) failure(died_allcause)
end

program define post_coefficients
    args handle dataset_name model_label exposure_spec
    local coef_list : colnames e(b)
    scalar n_obs = e(N)
    capture scalar n_fail = e(N_fail)
    if _rc scalar n_fail = .
    foreach coef of local coef_list {
        if "`coef'" != "_cons" {
            scalar beta = _b[`coef']
            scalar se = _se[`coef']
            scalar hr = exp(beta)
            scalar ci_lower = exp(beta - invnormal(.975) * se)
            scalar ci_upper = exp(beta + invnormal(.975) * se)
            scalar p_value = 2 * normal(-abs(beta / se))
            post `handle' ("`dataset_name'") ("`model_label'") ("`exposure_spec'") ("`coef'") (hr) (ci_lower) (ci_upper) (p_value) (n_obs) (n_fail)
        }
    }
end

program define post_ph_diagnostics
    args handle dataset_name model_label exposure_spec exposure_var

    local global_rc = .
    local global_chi2 = .
    local global_df = .
    local global_p = .
    local global_status "not run"
    capture noisily estat phtest, detail
    local global_rc = _rc
    if `global_rc' == 0 {
        local global_status "completed"
        capture local global_chi2 = r(chi2)
        capture local global_df = r(df)
        capture local global_p = r(p)
        if "`global_chi2'" == "" local global_chi2 = .
        if "`global_df'" == "" local global_df = .
        if "`global_p'" == "" local global_p = .
    }
    else {
        local global_status "failed; see Stata log"
        note_issue "Refined Cox PH diagnostic failed for `dataset_name' `model_label' `exposure_spec' global test with Stata return code `global_rc'."
    }
    post `handle' ("`dataset_name'") ("`model_label'") ("`exposure_spec'") ("global") (`global_chi2') (`global_df') (`global_p') (`global_rc') ("`global_status'")

    local posted_exposure 0
    if `global_rc' == 0 {
        tempname phdetail
        capture matrix `phdetail' = r(phtest)
        if !_rc {
            local ph_rows : rownames `phdetail'
            local ph_n = rowsof(`phdetail')
            local ph_k = colsof(`phdetail')
            if `ph_k' >= 4 {
                forvalues j = 1/`ph_n' {
                    local ph_term : word `j' of `ph_rows'
                    if strpos("`ph_term'", "`exposure_var'") > 0 {
                        scalar ph_chi2 = `phdetail'[`j',2]
                        scalar ph_df = `phdetail'[`j',3]
                        scalar ph_p = `phdetail'[`j',4]
                        post `handle' ("`dataset_name'") ("`model_label'") ("`exposure_spec'") ("`ph_term'") (ph_chi2) (ph_df) (ph_p) (`global_rc') ("detail completed")
                        local posted_exposure 1
                    }
                }
            }
        }
    }

    if `posted_exposure' == 0 {
        local msa_status "see detailed PH test in Stata log"
        post `handle' ("`dataset_name'") ("`model_label'") ("`exposure_spec'") ("`exposure_var'") (.) (.) (.) (0) ("`msa_status'")
    }
end

program define fit_refined_model
    args result_handle ph_handle dataset_name model_label exposure_spec exposure_var model_terms strata_terms

    display as text _n "Fitting `dataset_name' | `model_label' | `exposure_spec'"
    local opts "vce(robust)"
    if "`strata_terms'" != "" {
        local opts "`opts' strata(`strata_terms')"
    }

    capture noisily stcox `model_terms', `opts'
    if _rc {
        note_issue "Refined Cox model failed: dataset=`dataset_name'; model=`model_label'; exposure=`exposure_spec'; Stata return code `_rc'."
    }
    else {
        post_coefficients `result_handle' "`dataset_name'" "`model_label'" "`exposure_spec'"
        post_ph_diagnostics `ph_handle' "`dataset_name'" "`model_label'" "`exposure_spec'" "`exposure_var'"
    }
end

program define write_refined_report
    args result_file ph_file report_file

    preserve
    use "`result_file'", clear
    keep if strpos(term, "msa_cat5") > 0 | strpos(term, "msa_optimal_cat") > 0 | strpos(term, "insufficient_msa") > 0

    local run_date "`c(current_date)'"
    local run_time "`c(current_time)'"
    local nrows = _N

    file open rep using "`report_file'", write replace text
    file write rep "# Interpretacion de modelos Cox refinados" _n _n
    file write rep "Generado por code/stata/03_refined_cox_models.do el `run_date' `run_time'." _n _n
    file write rep "No se calcularon PAFs, muertes atribuibles, YLL, esperanza de vida ni costos." _n _n
    file write rep "## Estimaciones de MSA" _n _n
    file write rep "| Dataset | Modelo | Especificacion | Termino | HR | IC 95% | p |" _n
    file write rep "|---|---|---|---|---:|---:|---:|" _n
    if `nrows' == 0 {
        file write rep "| No rows | No rows | No rows | No rows | . | .-. | . |" _n
    }
    else {
        forvalues i = 1/`nrows' {
            local dataset_i = dataset[`i']
            local model_i = model_label[`i']
            local spec_i = exposure_spec[`i']
            local term_i = term[`i']
            local hr_i : display %6.3f hazard_ratio[`i']
            local lo_i : display %6.3f ci_lower[`i']
            local hi_i : display %6.3f ci_upper[`i']
            local p_i : display %9.4g p_value[`i']
            file write rep "| `dataset_i' | `model_i' | `spec_i' | `term_i' | `hr_i' | `lo_i'-`hi_i' | `p_i' |" _n
        }
    }

    file write rep _n "## Lectura substantiva" _n _n
    file write rep "- La especificacion de rango optimo usa 2-4 veces/semana como referencia. HRs mayores que 1 para 0-1 o 5+ indican menor mortalidad relativa en el rango 2-4." _n
    file write rep "- La especificacion guideline usa insufficient_msa=0 como referencia; HR>1 para 1.insufficient_msa indica mayor mortalidad con MSA insuficiente." _n
    file write rep "- Comparar Model A-D para evaluar si edad como escala temporal y estratificacion por sexo/anio cambian las estimaciones." _n
    file write rep "- Comparar main con lag24 para evaluar sensibilidad a causalidad reversa temprana." _n _n

    file write rep "## Diagnosticos PH" _n _n
    file write rep "Los resultados capturados automaticamente estan en outputs/tables/refined_cox_ph_diagnostics.csv. Los tests detallados de Schoenfeld quedan en outputs/logs/03_refined_cox_models.log." _n _n

    file write rep "## Recomendacion antes de burden" _n _n
    file write rep "No avanzar a PAFs o burden hasta revisar que el patron 2-4 veces/semana y el contraste de MSA insuficiente sean robustos a las especificaciones age-as-time-scale, estratificacion y lag-24, y que las violaciones PH de los terminos MSA esten ausentes o justificadas." _n _n

    file write rep "## Ecuacion estimada" _n _n
    file write rep "Con edad como escala temporal, el modelo estimado es:" _n _n
    file write rep "h_i(a | X_i) = h_0(a) * exp(beta_1 MSA_i + beta_2 X_i)" _n
    file write rep _n
    file write rep "donde a es edad, age_entry es la edad al inicio de seguimiento y age_exit es edad basal + seguimiento. En modelos estratificados, h_0(a) se permite variar por sexo, anio de encuesta, o ambos." _n
    file close rep
    restore
end

capture confirm file "`main_data'"
if _rc {
    note_issue "Refined Cox models stopped: main complete-case dataset not found at `main_data'."
    exit 601
}

tempfile refined_results refined_ph
tempname result_handle ph_handle
postfile `result_handle' str20 dataset str40 model_label str40 exposure_spec str100 term double hazard_ratio ci_lower ci_upper p_value n_obs n_fail using "`refined_results'", replace
postfile `ph_handle' str20 dataset str40 model_label str40 exposure_spec str40 ph_test double chi2 df p_value stata_rc str80 status using "`refined_ph'", replace

local cov_common "i.race_ethnicity_n i.education_n i.poverty_n i.marital_status_n i.smoking_status_n i.alcohol_use_n i.bmi_cat_n i.self_rated_health_n i.aerobic_category_n i.diabetes i.hypertension i.cvd_history i.cancer_history"
local cov_a "`cov_common' i.sex_n i.year"
local cov_b "`cov_common' i.year"
local cov_c "`cov_common' i.sex_n"
local cov_d "`cov_common'"

use "`main_data'", clear
prepare_refined_data

foreach exposure_spec in original optimal guideline {
    if "`exposure_spec'" == "original" {
        local exposure_label "Original msa_cat5"
        local exposure_var "msa_cat5"
        local exposure_terms "ib0.msa_cat5"
    }
    if "`exposure_spec'" == "optimal" {
        local exposure_label "Optimal range"
        local exposure_var "msa_optimal_cat"
        local exposure_terms "ib1.msa_optimal_cat"
    }
    if "`exposure_spec'" == "guideline" {
        local exposure_label "Guideline"
        local exposure_var "insufficient_msa"
        local exposure_terms "ib0.insufficient_msa"
    }

    fit_refined_model `result_handle' `ph_handle' "main" "Model A age time" "`exposure_label'" "`exposure_var'" "`exposure_terms' `cov_a'" ""
    fit_refined_model `result_handle' `ph_handle' "main" "Model B strata sex" "`exposure_label'" "`exposure_var'" "`exposure_terms' `cov_b'" "sex_n"
    fit_refined_model `result_handle' `ph_handle' "main" "Model C strata year" "`exposure_label'" "`exposure_var'" "`exposure_terms' `cov_c'" "year"
    fit_refined_model `result_handle' `ph_handle' "main" "Model D strata sex year" "`exposure_label'" "`exposure_var'" "`exposure_terms' `cov_d'" "sex_n year"
}

capture confirm file "`lag_data'"
if _rc {
    note_issue "Refined Cox lag-24 models skipped: lag-24 complete-case dataset not found at `lag_data'."
}
else {
    use "`lag_data'", clear
    prepare_refined_data
    foreach exposure_spec in original optimal guideline {
        if "`exposure_spec'" == "original" {
            local exposure_label "Original msa_cat5"
            local exposure_var "msa_cat5"
            local exposure_terms "ib0.msa_cat5"
        }
        if "`exposure_spec'" == "optimal" {
            local exposure_label "Optimal range"
            local exposure_var "msa_optimal_cat"
            local exposure_terms "ib1.msa_optimal_cat"
        }
        if "`exposure_spec'" == "guideline" {
            local exposure_label "Guideline"
            local exposure_var "insufficient_msa"
            local exposure_terms "ib0.insufficient_msa"
        }

        fit_refined_model `result_handle' `ph_handle' "lag24" "Model E lag24 age time" "`exposure_label'" "`exposure_var'" "`exposure_terms' `cov_a'" ""
        fit_refined_model `result_handle' `ph_handle' "lag24" "Model E lag24 strata sex year" "`exposure_label'" "`exposure_var'" "`exposure_terms' `cov_d'" "sex_n year"
    }
}

postclose `result_handle'
postclose `ph_handle'

use "`refined_results'", clear
export delimited using "`result_csv'", replace

use "`refined_ph'", clear
export delimited using "`ph_csv'", replace

write_refined_report "`refined_results'" "`refined_ph'" "`report_md'"

display as text _n "Refined Cox models complete. No PAFs, attributable deaths, YLL, life expectancy, or costs computed."
log close
