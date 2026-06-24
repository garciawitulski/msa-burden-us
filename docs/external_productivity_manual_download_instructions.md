# External Productivity Inputs Needed

Productivity losses have not been computed because the project does not yet
contain an official, documented input file at:

`data/external/us_productivity_inputs_by_age_sex.csv`

Create that file with these columns:

- `year`
- `sex`
- `age_group`
- `employment_rate`
- `annual_earnings`
- `productive_years_remaining`
- `source`
- `notes`

Required age groups are 18-34, 35-44, 45-54, 55-64, 65-74, and 75+ by sex.
The main analysis will use ages 18-64. The 65-74 group is used only as a
sensitivity analysis when official employment and earnings inputs are present.
The 75+ group is not assigned productivity losses unless a manuscript decision
explicitly justifies doing so with official data.

Recommended official sources:

1. BLS Current Population Survey annual averages for employment by age and sex.
   Candidate tables include annual-average CPS employment status tables and
   employed/unemployed full-time and part-time worker tables.
   Start here: https://www.bls.gov/cps/tables.htm
2. BLS CPS annual-average usual weekly earnings by age and sex.
   Candidate table: CPS annual average table 37, median weekly earnings of
   full-time wage and salary workers by selected characteristics.
   2024 table: https://www.bls.gov/cps/data/aa2024/cpsaat37.htm
3. If choosing annual earnings or labor income from Census/ACS instead of BLS
   weekly earnings, use a documented ACS table or PUMS extraction and record the
   exact table, variables, vintage, and conversion to annual dollars.

Do not fill the template with approximate or invented values. Every row should
cite the official source and year used. If weekly earnings are used, document the
annualization rule, for example `annual_earnings = weekly_earnings * 52`.
