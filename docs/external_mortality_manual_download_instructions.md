# Manual CDC WONDER Mortality Download Instructions

Automatic CDC WONDER extraction did not complete. Do not fabricate death counts.

Use CDC WONDER: Underlying Cause of Death, 2018-2024, Single Race.

Required output: `data/external/us_allcause_deaths_by_age_sex.csv`

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
3. Year: latest final year available, preferably 2024 if final.
4. Cause of death: All Causes.
5. Sex: Female and Male.
6. Ages: aggregate exactly to 18-34, 35-44, 45-54, 55-64, 65-74, and 75+.
7. Export deaths and population.
8. Save to `data/external/us_allcause_deaths_by_age_sex.csv`.
