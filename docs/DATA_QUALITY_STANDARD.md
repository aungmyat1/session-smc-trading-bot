# Data Quality Standard

`scripts/dataset_quality_check.py` writes `artifacts/data_quality_report.json`.

Release thresholds:

- `missing_pct <= 0.1`
- `duplicate_pct <= 0.01`
- `timestamp_errors == 0`

The checker also records OHLC consistency failures. Any breached threshold returns a non-zero process exit and blocks release packaging.

