version 17
clear all
set more off

capture confirm file "data/processed/msa_survival_full.dta"
if _rc {
    capture confirm file "../../data/processed/msa_survival_full.dta"
    if _rc {
        display as error "Could not find data/processed/msa_survival_full.dta. Run the Python build script first."
        exit 601
    }
    local data_path "../../data/processed/msa_survival_full.dta"
}
else {
    local data_path "data/processed/msa_survival_full.dta"
}

use "`data_path'", clear

describe
summarize
tab year, missing
tab msa_cat5, missing
tab msa_guideline, missing
tab insufficient_msa, missing
tab died_allcause, missing
summarize followup_time_months followup_time_years

capture confirm variable weight_mortality
if _rc {
    display as error "weight_mortality not found."
    exit 111
}

stset followup_time_years [pweight=weight_mortality], failure(died_allcause)
stsum
sts graph, by(msa_cat5) name(msa_cat5_survival_check, replace)

display as text "Survival dataset can be stset. No final models estimated."
