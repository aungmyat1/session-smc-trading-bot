# Dataset Versioning

The v2 immutable dataset directory is `datasets/professional_3y_4symbol_v2`.

Required files:

- `manifest.json`
- `metadata.yaml`
- `checksums.json`

Create them with:

```bash
python scripts/create_dataset_manifest.py
python scripts/generate_checksums.py
```

The manifest records dataset ID, build time, sources, symbols, timeframes, record counts, feature counts, quality metrics, and Git commit. Checksums include per-file SHA256 values plus a dataset-level hash.

