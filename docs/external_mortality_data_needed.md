# External mortality data needed

Official US all-cause death counts are required before attributable deaths can
be estimated. The preferred source is NCHS/CDC WONDER or another official NCHS
mortality file.

Required columns:

- `year`
- `sex`
- `age_group`
- `deaths_allcause`
- `source`
- `notes`

The `sex` and `age_group` values should match the processed NHIS burden strata
used in `outputs/tables/msa_prevalence_insufficient.csv`. Do not enter
estimated or placeholder death counts.
