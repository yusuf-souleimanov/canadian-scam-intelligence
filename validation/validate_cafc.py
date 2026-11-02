"""Validation checks for the CAFC fraud dataset.

Run from the interac-scam-intel folder:
    .venv/Scripts/python.exe validation/validate_cafc.py

Each check prints PASS, WARN or FAIL:
    PASS = the data is what we expect
    WARN = not an error, but a limitation to document (see validation_log.md)
    FAIL = something is wrong and must be fixed before reporting numbers
"""
import pandas as pd

RAW_CSV = "data/raw/cafc.csv"
CLEAN_PKL = "data/cafc_clean.pkl"

# Short names for the English columns, by position (same idea as COLUMNS in intel/trends.py).
# Using positions avoids typing the long bilingual names with accents.
COLUMNS = {
    0: "id", 1: "date", 4: "country", 6: "province", 8: "category",
    10: "solicitation", 12: "gender", 16: "age_range", 17: "complaint_type",
    19: "victims", 20: "loss_text",
}

# Values that mean "we don't know", found in check 2
PLACEHOLDERS = ["Not Specified", "Not Available", "Unknown", "Prefer not to say",
                "Other/unknown", "'Not Available / non disponible"]

results = []  # every check adds one (status, name, detail) here


def check(status, name, detail):
    results.append(status)
    print(f"[{status}] {name}: {detail}")


# ---------- Load ----------
raw = pd.read_csv(RAW_CSV, encoding="cp1252", low_memory=False)
df = raw.iloc[:, list(COLUMNS)].copy()
df.columns = list(COLUMNS.values())

dates = pd.to_datetime(df["date"], errors="coerce")
loss = pd.to_numeric(df["loss_text"].str.replace(r"[$,]", "", regex=True), errors="coerce")
is_canada = df["country"] == "Canada"

clean = pd.read_pickle(CLEAN_PKL)

print(f"Raw file: {len(df):,} rows\n")

# ---------- Check 1: Row count reconciliation ----------
non_canada = (~is_canada).sum()
bad_dates = dates.isna().sum()
expected_rows = len(df) - non_canada - bad_dates
status = "PASS" if expected_rows == len(clean) else "FAIL"
check(status, "Row reconciliation",
      f"{len(df):,} raw - {non_canada:,} non-Canada - {bad_dates:,} bad dates = {expected_rows:,}; "
      f"cleaned file has {len(clean):,}")

not_specified_rows = (df["country"] == "Not Specified").sum()
check("WARN", "Country unknown",
      f"{not_specified_rows:,} of the {non_canada:,} dropped rows are 'Not Specified', not foreign")

# ---------- Check 2: Nulls and disguised nulls ----------
true_nulls = df.isna().sum().sum()
check("PASS" if true_nulls == 0 else "FAIL", "True nulls", f"{true_nulls:,} empty cells")

for col in ["country", "province", "solicitation", "gender", "age_range"]:
    hidden = df[col].isin(PLACEHOLDERS).sum()
    if hidden > 0:
        check("WARN", f"Disguised nulls in {col}", f"{hidden:,} rows ({hidden / len(df):.1%})")

# ---------- Check 3: Duplicates ----------
dup_ids = df["id"].duplicated().sum()
check("PASS" if dup_ids == 0 else "FAIL", "Duplicate IDs", f"{dup_ids:,}")

# Use all 21 raw columns here: fewer columns would make more rows look identical
no_id = raw.drop(columns=[raw.columns[0]])
dup_rows = no_id.duplicated()
dup_share = loss[dup_rows].sum() / loss.sum()
# Under 1% of losses is treated as immaterial
status = "WARN" if dup_share < 0.01 else "FAIL"
check(status, "Identical rows (except ID)",
      f"{dup_rows.sum():,} rows holding ${loss[dup_rows].sum():,.2f} ({dup_share:.2%} of all losses)")

# ---------- Check 4: Ranges ----------
in_range = dates.min() >= pd.Timestamp("2021-01-01") and dates.max() <= pd.Timestamp("2025-09-30")
check("PASS" if in_range else "FAIL", "Date range", f"{dates.min():%Y-%m-%d} to {dates.max():%Y-%m-%d}")

unreadable = loss.isna().sum()
check("PASS" if unreadable == 0 else "FAIL", "Unreadable losses", f"{unreadable:,}")

negatives = (loss < 0).sum()
check("PASS" if negatives == 0 else "FAIL", "Negative losses", f"{negatives:,}")

biggest = df[loss == loss.max()].iloc[0]
check("WARN", "Largest loss",
      f"${loss.max():,.2f} (ID {biggest['id']}, category {biggest['category']}), kept and flagged")

# victims should be 1 exactly when the complaint type is Victim
victims_match = (df["victims"] == 1) == (df["complaint_type"] == "Victim")
check("PASS" if victims_match.all() else "FAIL", "Victims column matches complaint type",
      f"{(~victims_match).sum():,} contradictions")

# ---------- Check 5: Loss total reconciliation ----------
canada_loss = loss[is_canada].sum()
clean_loss = clean["loss"].sum()
# Compare rounded to the cent, because decimals stored by computers can differ in tiny fractions
status = "PASS" if round(canada_loss, 2) == round(clean_loss, 2) else "FAIL"
check(status, "Loss reconciliation", f"raw Canada ${canada_loss:,.2f} vs cleaned ${clean_loss:,.2f}")

not_specified_loss = loss[df["country"] == "Not Specified"].sum()
check("WARN", "Possible understatement",
      f"${not_specified_loss:,.2f} in 'Not Specified' rows, up to {not_specified_loss / canada_loss:.1%} "
      f"more than the Canada total; report it as a lower bound")

# ---------- Summary ----------
print(f"\nSummary: {results.count('PASS')} PASS, {results.count('WARN')} WARN, {results.count('FAIL')} FAIL")
