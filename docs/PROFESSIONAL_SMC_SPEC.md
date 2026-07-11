# Professional SMC Spec

`scripts/extract_professional_smc_features.py` writes `research/smc_events/<SYMBOL>.parquet`.

Current generated labels:

- `BOS`
- `FVG`
- `LiquiditySweep`
- `Displacement`

Reserved labels for later richer extraction are `CHoCH`, `OB`, `Mitigation`, `EQH`, `EQL`, `PremiumDiscount`, and `SessionOpen`.

The extractor is deterministic, uses only past rolling windows, and avoids importing the historically fragile `session_smc.fvg` module directly.

