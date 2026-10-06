CSV POC DATA DIRECTORY

MASTER_TABLE.csv is kept exactly in the user's existing table-level format.
Place data dumps here using the exact Oracle table name plus .csv, for example:
  T_MCH_COKE.csv
  T_MCH_PUSH_CURRENT_LOG.csv
  T_MSU_FLUE_MEASUREMENT.csv

Requirements:
1. CSV headers must exactly match column names documented in MASTER_TABLE.csv.
2. Save timestamps in a pandas-readable format such as 2026-07-01 14:30:00.
3. Keep each PoC file below MAX_CSV_ROWS (default 500,000).
4. Do not add a data file whose table is absent from MASTER_TABLE.csv.
5. T_MCH_PUSH_CURRENT_LOG metadata currently documents only ID_SEQ_COKE. Add all real current/timestamp column descriptions to MASTER_TABLE.csv before analyzing them.
