# Manual CDC WONDER Mortality Download Instructions For Premature 30-69 Analysis

Automatic CDC WONDER extraction did not complete. Do not fabricate death counts.

Use CDC WONDER: Underlying Cause of Death, 2018-2024, Single Race.

Required output: `data/external/us_allcause_deaths_by_age_sex_premature_30_69.csv`

Required columns:

- `year`
- `sex`
- `age_group`
- `deaths_allcause`
- `population`
- `source`
- `notes`

Manual query:

1. Dataset: Underlying Cause of Death, 2018-2024, Single Race.
2. Geography: United States.
3. Year: 2024 final mortality.
4. Cause of death: All Causes.
5. Group or filter by sex.
6. Export deaths and population for exact age groups 30-34, 35-44, 45-54, 55-64, and 65-69.
7. Save to `data/external/us_allcause_deaths_by_age_sex_premature_30_69.csv`.
