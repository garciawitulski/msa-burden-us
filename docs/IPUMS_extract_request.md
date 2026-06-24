# Manual IPUMS NHIS Extract Request

Generated: 2026-04-29T16:49:48

No IPUMS_API_KEY environment variable was available, so this project did not
download or fabricate any data. Create the extract manually from IPUMS Health
Surveys: NHIS, then place the downloaded data and all metadata/codebook files in
`data/raw/`.

## Dataset

- IPUMS Health Surveys: NHIS
- Unit of analysis: person records
- Extract structure: rectangularized on person records (`P`)
- Data format: CSV if available, with DDI XML and basic codebook included
- Stata command file should also be downloaded when offered

## Samples to select

Select the NHIS samples from 1997 through 2018. These are the widest planned
years for the first-stage dataset because the IPUMS documentation indicates
adult strengthening activity is available from 1997 onward, while the 2019 LMF
update includes NHIS mortality follow-up for participants through the 2018 NHIS.
The 1997 physical-activity variables need special review because some aerobic
variables begin in quarters 3-4.

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

## Variables to select

Select these exact IPUMS NHIS variable mnemonics. Some identifiers/design flags
may be preselected automatically by IPUMS; keep them in the extract if offered.

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

## Metadata/codebooks required before cleaning

Download and keep these files next to the data in `data/raw/`:

- DDI XML codebook
- Basic codebook
- Stata command file, if offered
- Any IPUMS extract JSON or request metadata

The cleaning script intentionally inspects the downloaded metadata/codebooks
before constructing variables. If a required variable cannot be verified from
the metadata and data columns, the script stops and writes
`outputs/logs/issues_to_resolve.md`.

## Public-use follow-up time note

The preferred survival time variable is an exact public-use person-month
follow-up variable if it is available in the extract. IPUMS NHIS mortality
documentation commonly exposes year/quarter of death variables (`MORTDODY`,
`MORTDODQ`) and final vital status (`MORTSTAT`). If exact person-month follow-up
is not in the IPUMS extract, the project script constructs an approximate
quarter-based follow-up time using `YEAR`, `QUARTER`, `MORTDODY`, and
`MORTDODQ`, and records this limitation in the variable dictionary and issue log.

## Year inclusion table to create after download

After data are downloaded, run:

```powershell
python code/python/01_data_inventory.py
python code/python/03_build_msa_survival_dataset.py
python code/python/04_quality_checks.py
```

The build and quality scripts will create a year inclusion table documenting
which survey years are included and why.

## Official documentation checked

- IPUMS API microdata docs: https://developer.ipums.org/docs/v2/apiprogram/apis/microdata/
- IPUMS API extract workflow: https://developer.ipums.org/docs/v2/workflows/create_extracts/microdata/
- IPUMS NHIS sample IDs: https://nhis.ipums.org/nhis-action/samples/sample_ids
- IPUMS NHIS STRONGFWK: https://nhis.ipums.org/nhis-action/variables/STRONGFWK
- IPUMS NHIS MORTELIG/Mortality group: https://nhis.ipums.org/nhis-action/variables/group/mortality_mortality
- IPUMS NHIS MORTWTSA: https://nhis.ipums.org/nhis-action/variables/MORTWTSA/ajax_enum_text
- IPUMS NHIS physical activity group: https://nhis.ipums.org/nhis-action/variables/group/behavior_pa
- NCHS public-use LMF description: https://nhis.ipums.org/nhis/resources/public-use-linked-mortality-file-description.pdf
