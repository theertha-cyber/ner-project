# Uploaded spreadsheet files: tenant notes

Tenant administrators can upload spreadsheets on **Settings → Data Sources → Uploaded files**. After an
administrator reviews and publishes a file, the chatbot answers questions about it exactly: totals, counts,
averages, filters and rankings. These notes cover what you can upload, what happens to the data, and where it
is stored. The design is in ADR-018 and ADR-019.

## Formats and limits

| | |
|---|---|
| Accepted | `.csv` and `.xlsx`. Each upload is one table: for `.xlsx`, the chosen sheet (the first sheet by default). |
| Refused | `.xls`, macro-enabled `.xlsm`, and every other extension (`UNSUPPORTED_FILE_TYPE`). |
| Size | 100 MB per file (`FILE_TOO_LARGE`). The limit applies while the file is being received. |
| Rows | 1,000,000 data rows per file. Larger files fail with `ROW_LIMIT_EXCEEDED`. |
| Files | 20 per tenant, not counting deleted files (`FILE_LIMIT_REACHED`). |
| Sheet layout | One header row. Merged cells in the header area, or a blank header cell, fail with `UNSUPPORTED_SHEET_LAYOUT`. |

Formulas are never evaluated. An `.xlsx` cell holding a formula contributes the value Excel last saved for it,
so save the workbook in Excel before you upload it.

## From upload to chat

1. **Profiling.** The platform reads every row, turns headers into safe column names (for example,
   `2024 Revenue ($)` becomes `c_2024_revenue`), and suggests a type for each column. Values such as `007`
   stay text. Dates that could be either day-first or month-first are not guessed: you choose the format.
2. **Review.** You can rename columns, change types, pick date formats, exclude columns, describe the table
   and its columns, and approve example values. The load report shows how many rows will load and which rows
   would be rejected. The preview shows the first 20 rows as they will be stored.
3. **Publish.** You need a table description and a date format for every included date column before you
   can publish. Rows that do not match the approved types are dropped, and the load report counts them.
4. **Chat.** Only published files are offered to the chatbot. Excluded columns do not exist for the
   chatbot. It can read one file per question and cannot combine two files.

To replace a file, use **Upload new version**. The published version keeps answering questions until you
publish the new one. **Delete** stops chat using the file immediately and removes every stored copy.

Answers cite the file name, the version, and the columns used. Citations never include row values or the
values you filtered on.

## Where your data is stored (residency)

Uploaded files are stored in the platform's object storage for **every** tenant, whatever your data-plane
mode. This includes both the original file and the query copy made when you publish. File metadata and
published column definitions are kept in the platform's control database.

If your tenant uses a **tenant-owned** data plane, this is an exception to that arrangement. Your documents
and conversations stay in your own database, but uploaded spreadsheets do not. The portal shows this notice
above the upload control. **Do not upload files that must stay in your own environment.** No tenant-owned
object store exists yet. When one does, a new decision will supersede ADR-019 and existing files will be
migrated.

## Turning the feature off

Operators can set `NER_TABULAR_FILES_ENABLED=false` to turn the feature off. This hides the section, refuses
uploads, and removes the chat tool. Chat then behaves exactly as it did before this feature existed. Stored
files are kept until someone deletes them explicitly.
