# Manual IPUMS NHIS Extract Request

Generated: 2026-06-24T17:52:07

Create the extract manually from IPUMS Health Surveys: NHIS, then place the downloaded data and metadata in `data/raw/`.

## Samples

- ih1997 (1997 NHIS)
- ih1998 (1998 NHIS)
- ih1999 (1999 NHIS)
- ih2000 (2000 NHIS)
- ih2001 (2001 NHIS)
- ih2002 (2002 NHIS)
- ih2003 (2003 NHIS)
- ih2004 (2004 NHIS)
- ih2005 (2005 NHIS)
- ih2006 (2006 NHIS)
- ih2007 (2007 NHIS)
- ih2008 (2008 NHIS)
- ih2009 (2009 NHIS)
- ih2010 (2010 NHIS)
- ih2011 (2011 NHIS)
- ih2012 (2012 NHIS)
- ih2013 (2013 NHIS)
- ih2014 (2014 NHIS)
- ih2015 (2015 NHIS)
- ih2016 (2016 NHIS)
- ih2017 (2017 NHIS)
- ih2018 (2018 NHIS)

## Variables

- YEAR
- SERIAL
- NHISPID
- QUARTER
- ASTATFLG
- STRATA
- PSU
- SAMPWEIGHT
- PERWEIGHT
- MORTWT
- MORTWTSA
- MORTELIG
- MORTSTAT
- MORTDODY
- MORTDODQ
- MORTUCODLD
- MORTUCOD
- STRONGFNO
- STRONGFTP
- STRONGFWK
- MOD10FNO
- MOD10FTP
- MOD10FWK
- MOD10DNO
- MOD10DTP
- MOD10DMIN
- VIG10FNO
- VIG10FTP
- VIG10FWK
- VIG10DNO
- VIG10DTP
- VIG10DMIN
- AGE
- SEX
- RACEA
- HISPETH
- EDUC
- POVERTY
- MARSTAT
- REGION
- BMICALC
- SMOKESTATUS2
- ALCSTAT1
- ALCSTAT2
- HEALTH
- DIABETICEV
- HYPERTENEV
- CHEARTDIEV
- HEARTATTEV
- STROKEV
- CANCEREV

## Required metadata

- DDI XML codebook
- Basic codebook
- Stata command file, if offered
- Extract JSON/request metadata

## After download

```powershell
Rscript code/r/pipeline/01_data_inventory.R
Rscript code/r/pipeline/03_build_msa_survival_dataset.R
Rscript code/r/pipeline/04_quality_checks.R
```

## Official documentation

- IPUMS API microdata docs: https://developer.ipums.org/docs/v2/apiprogram/apis/microdata/
- IPUMS API extract workflow: https://developer.ipums.org/docs/v2/workflows/create_extracts/microdata/
- IPUMS NHIS sample IDs: https://nhis.ipums.org/nhis-action/samples/sample_ids
- IPUMS NHIS mortality variables: https://nhis.ipums.org/nhis-action/variables/group/mortality_mortality
- IPUMS NHIS physical activity group: https://nhis.ipums.org/nhis-action/variables/group/behavior_pa
