import pandas as pd
from pathlib import Path

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

INPUT_FILE = "oha_secretary_decisions.csv"
OUTPUT_FILE = "oha_secretary_decisions_salesforce.csv"

DATE_COLUMN = "Date"
YEAR_COLUMN = "Year"

# --------------------------------------------------
# LOAD CSV
# --------------------------------------------------

script_folder = Path(__file__).resolve().parent

input_path = script_folder / INPUT_FILE
output_path = script_folder / OUTPUT_FILE

df = pd.read_csv(input_path)

print(f"Loaded {len(df)} rows from {INPUT_FILE}")

# --------------------------------------------------
# VALIDATE REQUIRED COLUMNS
# --------------------------------------------------

for column in [DATE_COLUMN, YEAR_COLUMN]:
    if column not in df.columns:
        raise ValueError(
            f"Required column '{column}' was not found."
        )

# --------------------------------------------------
# CONVERT DATES
# --------------------------------------------------

converted_dates = []

for index, row in df.iterrows():
    original_date = str(row[DATE_COLUMN]).strip()

    if pd.isna(row[DATE_COLUMN]) or original_date == "":
        converted_dates.append("")
        continue

    try:
        # Strictly expect dates like:
        # 5-Aug-26
        # 14-Jul-26
        # 30-May-89

        parsed = pd.to_datetime(
            original_date,
            format="%d-%b-%y",
            errors="raise"
        )

        # Use the explicit Year column to avoid problems with
        # Python's two-digit-year century cutoff.
        full_year = int(row[YEAR_COLUMN])

        salesforce_date = (
            f"{full_year:04d}-"
            f"{parsed.month:02d}-"
            f"{parsed.day:02d}"
        )

        converted_dates.append(salesforce_date)

    except (ValueError, TypeError) as error:
        raise ValueError(
            f"Invalid date on CSV row {index + 2}: "
            f"{original_date!r}. "
            "Expected format such as 5-Aug-26."
        ) from error

df[DATE_COLUMN] = converted_dates

# --------------------------------------------------
# SAVE SALESFORCE CSV
# --------------------------------------------------

df.to_csv(
    output_path,
    index=False,
    encoding="utf-8-sig"
)

print()
print("SUCCESS")
print(f"Rows processed: {len(df)}")
print(f"Salesforce CSV: {output_path}")
