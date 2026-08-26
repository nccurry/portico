# Google Sheets data schema

Tiller Streamlit reads four tabs and ignores unknown columns. Column names are
case-sensitive.

## Transactions

Required columns:

`Date`, `Category`, `Amount`, `Account`, `Month`, `Week`, `Full Description`,
`Institution`, `Account #`, `Date Added`, and `Categorized Date`.

Dates must be values that pandas can parse. Amounts may contain dollar signs and
commas. Tiller expenses are normally negative and income is normally positive.

The app joins `Group`, `Type`, and `Hide From Reports` from Categories. Values of
those columns already present in Transactions are replaced by the joined values.
An unknown category is placed in the `Uncategorized` group.

## Balance History

Required columns:

`Date`, `Time`, `Balance`, `Account`, `Account #`, `Account ID`, `Institution`,
`Class`, `Month`, `Week`, and `Date Added`.

The app also uses account type, status, and group columns when provided by a
standard Tiller sheet.

## Categories

Required columns:

`Category`, `Group`, `Type`, and `Hide From Reports`.

Columns after those fields that can be parsed as dates are treated as monthly
budget columns. Budget values may contain dollar signs and commas.

## Accounts

The sheet must contain at least four columns. The first four columns are treated
as `Account`, `Class Override`, `Group`, and `Hide`. Additional columns are
ignored.

## Demo provenance

The files under `demo/data/` are fully synthetic. They are the shared source for
the public demo and integration tests. `REFERENCE_DATE.txt` fixes the reporting
date, and `INJECTED_ROWS.md` records deliberate recurring, duplicate, tie, and
zero-balance edge cases.
