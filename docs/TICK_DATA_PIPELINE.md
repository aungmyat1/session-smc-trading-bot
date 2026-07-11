# Tick Data Pipeline

`professional_3y_4symbol_v2` stores research tick data under `data/tick/<SYMBOL>/year=YYYY/month=MM/day=DD/ticks.parquet`.

Forex and gold rows use `timestamp_utc, symbol, bid, ask, spread, volume`. BTC rows use `timestamp_utc, symbol, price, quantity, side`. Files are Snappy Parquet and are written atomically by `scripts/normalize_tick_data.py`.

Primary commands:

```bash
python scripts/download_tick_data.py --dry-run
python scripts/normalize_tick_data.py
python scripts/validate_tick_data.py
```

The downloader is restartable because normalization overwrites only the affected daily partition after reading a raw monthly/source file.

