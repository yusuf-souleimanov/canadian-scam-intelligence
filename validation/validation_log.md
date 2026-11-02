# CAFC Validation Log

## Check 1: Row count reconciliation

Noticed 350,361 rows in the raw file, revealing an 83,808 gap to the 266,553. The filter in trends.py keeps only rows where Country = Canada and the date is present. Testing for the date cause, we see that there are no rows with NA for the date, so we can discount that as the cause. When we look at actual countries of the 83,808 that is filtered out by trends.py, the majority of them are not specified (78,765), and the remaining 5,043 are foreign countries (United States 2,399, India, others). This shows that the 83,808 may include Canadian reports, rather than just foreign countries being filtered, which means that the 266,553 may be understating additional Canadian reports. Kept the Canada-only filter, so the 266,553 will be treated as a lower bound.

## Check 2: Nulls and disguised nulls

Checking for the nulls in the dataset with .isnull().sum() revealed 0 nulls for each column. This prompted a deeper check for disguised nulls, given that for the Country column, "Not Specified" had 78,765 rows, which is a disguised null category. Running value_counts() on other columns revealed the following disguised nulls:

| Column | Placeholder values |
|---|---|
| Country | Not Specified 78,765 |
| Gender | Not Available 91,016, Unknown 1,065, Prefer not to say 516 |
| Age | Not Available / non disponible 104,676 |
| Province | Not Specified 82,484 |
| Solicitation | Other/unknown 101,691, Not Available 18,249 |

Prefer not to say (516 rows in Gender) is a valid entry, so it is listed separately in the count, but treated as unknown in any calculation. Other/unknown for the solicitation is being counted as a disguised null, because despite Other not being a true null, there is no reliable way to separate the unknown from the other. Deceased (188) is treated as an unknown age, since the victim's age wasn't recorded, so it is included in the upper bound. Business/Entreprise (27) is excluded as an age category. For impact, 30.4% of reports with a known victim age came from victims 60+ (29.9% of reports had no age recorded). Across all 350,361 reports, the 60+ share ranges from 21.3% to 51.2% depending on the unknowns. KPIs will exclude unknowns from the denominator and report the unknown share next to each figure.

## Check 3: Duplicates

We started by checking for duplicates based on the Number ID, and found 0 duplicate IDs. To make sure there were no duplicates hiding under different IDs, we also checked for rows that are identical in every column except the ID. We found 45,462 such rows. We did not delete them because the date is only a day, the age is a 10-year range, and the province is a whole province, so different people can produce identical rows. There is no name or time to prove that they are the same report. To test the worst case, we measured their losses: 44,469 of them have $0 loss, and the remaining 993 have a combined loss of $3,476,718, which is 0.13% of the $2,687,420,244 total across all 350,361 rows. The decision is to keep all the rows, since the possible overcount is immaterial to the dollar KPIs. Report counts may be slightly inflated, which is noted.

## Check 4: Ranges

For dates, we ran the minimum and maximum: January 2, 2021 to September 29, 2025, matching the expected coverage. For loss, there were 0 values that couldn't be read and 0 negatives, with a minimum of $0 and a maximum of $23,615,000. The $23.6M row is a Manitoba victim report from April 29, 2024, with the category Unknown and age, gender, language and solicitation all Not Available. We decided to keep it and flag it. It is included in total losses, but not in any scam-type KPI, since its category is unknown. For typical loss, the median will be used instead of the mean, so outliers like this one can't skew it. For Number of Victims, there are only 0 or 1. A crosstab with Complaint Type showed that 1 is always a Victim report, and all non-victim complaint types (Attempt, Incomplete, Other, Unknown) are 0, with no contradictions. The column acts as a victim flag rather than a count, and its 0s are not nulls.

## Check 5: Loss total reconciliation

The raw file has total losses of $2,687,420,243.97 across all rows, and $2,083,045,679.94 for Canada rows only. The cleaned file used by trends.py (cafc_clean.pkl) has 266,553 rows and total losses of $2,083,045,679.94, which matches the raw Canada total to the cent, so the cleaning did not lose, add or change any money in the rows it kept. The $604,374,564.03 that was dropped breaks down into $473,017,653.07 from rows with Country = Not Specified and $131,356,910.96 from foreign countries. Since the Not Specified rows may include Canadian reports, Canadian losses are between $2,083,045,679.94 and $2,556,063,333.01, up to 22.7% higher than the current figure. Unlike the 0.13% from possible duplicates in check 3, this is material. The Canada-only filter is kept, consistent with check 1, but total losses will be labelled as a lower bound on the scorecard, with the Not Specified amount shown next to it.
