# External Data Needed For Finer Life Expectancy Gain Estimates

The current life expectancy gain module can run with the validated broad adult
CDC WONDER mortality file:

- `data/external/us_allcause_deaths_by_age_sex.csv`

That file has age groups 18-34, 35-44, 45-54, 55-64, 65-74, and 75+. Therefore,
life expectancy gains are approximate abridged life-table estimates.

For a finer life-table estimate, manually export official CDC WONDER final
all-cause mortality for the latest final mortality year used in the burden
analysis, currently 2024:

1. Data source: CDC WONDER Underlying Cause of Death, 2018-2024, Single Race.
2. Geography: United States.
3. Year: 2024 final mortality.
4. Cause of death: All causes.
5. Group results by sex and fine age group.
6. Export deaths and population for: <1, 1-4, 5-9, 10-14, 15-17, 18-19,
   20-24, 25-29, 30-34, 35-39, 40-44, 45-49, 50-54, 55-59, 60-64, 65-69,
   70-74, 75-79, 80-84, and 85+.
7. Save the prepared file as
   `data/external/us_allcause_deaths_by_fine_age_sex.csv` with columns:
   `year`, `sex`, `age_group`, `age_start`, `age_end`, `deaths_allcause`,
   `population`, `source`, and `notes`.

Do not enter hand-estimated death counts or populations. Use official exported
CDC/NCHS values only.
