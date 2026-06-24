# Manual NCHS Life Table Download Instructions

Automatic NCHS life-table download did not complete. Do not fabricate life
expectancy values.

Preferred source: NCHS United States Life Tables, 2023, NVSR Volume 74, Number 6.

Required single-age output: `data/external/us_life_table_by_age_sex.csv`

Required columns:

- `year`
- `sex`
- `age`
- `remaining_life_expectancy`
- `source`
- `notes`

Then create `data/external/us_life_table_by_agegroup_sex.csv` using representative ages:

- 18-34: 25
- 35-44: 40
- 45-54: 50
- 55-64: 60
- 65-74: 70
- 75+: 80
