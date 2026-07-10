# Backup Retention Policy Review — `~/archives`

Date: 2026-07-06
Status: Review — no deletion performed or proposed for immediate execution
Related: `docs/vps/CLEANUP_PLAN.md` ("Archive First" section), `config/storage_policy.yaml`
(`retention.archives`)

## Inventory (`~/archives`, 513M total)

| Archive | Size | Date | Checksummed? |
|---|---:|---|---|
| `benchmark-bot_20260704T162435Z.tar.gz` | 4.0M | 2026-07-04 | Yes (`.sha256` present) |
| `forex-validate_20260704T162435Z.tar.gz` | 125M | 2026-07-04 | Yes |
| `home-backups_20260704T162435Z.tar.gz` | 111M | 2026-07-04 | Yes |
| `rotated-logs_20260704T162435Z.tar.gz` | 20M | 2026-07-04 | Yes |
| `simple-smc-ag-trading-bot_20260704T162435Z.tar.gz` | 228M | 2026-07-04 | Yes |
| `smc-test_20260704T162435Z.tar.gz` | 24M | 2026-07-04 | Yes |
| `data-execution-test-pollution-2026-07-06/` (directory, not tarball) | 1.6M | 2026-07-06 | No — appears to be a working directory, not a backup artifact |
| `systemd-units/` (directory) | 12K | 2026-07-04 | No |

## Age

All six checksummed backup tarballs share the **same timestamp** (`20260704T162435Z`)
— a single batch backup operation run on 2026-07-04, two days before this
audit. They are not stale by any reasonable retention standard yet.

## Duplication

Each tarball name corresponds to a distinct source (a benchmark bot project, a
forex validation project, a general home-directory backup, rotated logs, the
`simple-smc-ag-trading-bot` legacy repo, and an `smc-test` project) — **no
apparent duplication between the six tarballs**. `docs/vps/DISK_USAGE_REPORT.md`
separately notes that `simple-smc-ag-trading-bot` still exists as a live
745M directory on disk (`~/simple-smc-ag-trading-bot`) — meaning the
228M `simple-smc-ag-trading-bot_...tar.gz` backup and the live directory are
**redundant with each other**, though that's a live-vs-backup duplication, not
duplication within the archive set itself.

## Estimated recovery usefulness

- **High**: `home-backups`, `rotated-logs` — general safety nets, checksummed,
  recent, cheap to keep (131M combined).
- **Medium**: `forex-validate`, `smc-test`, `benchmark-bot` — project-specific
  backups; useful only if those projects are still active or under
  consideration for revival. No signal in this audit on whether they are.
- **Low-but-not-zero**: `simple-smc-ag-trading-bot` — the live directory this
  backs up already exists on disk (745M, per `DISK_USAGE_REPORT.md`), so this
  228M backup is only useful as protection against loss of the *live* copy,
  not as the only surviving copy of anything.

## Recommended retention policy

`config/storage_policy.yaml` sets `retention.archives.default_days: 90` and
`never_delete_without_owner_approval: true`. Concretely:

1. **Keep all six tarballs for now** — none is past a reasonable retention
   window (2 days old), and total size (513M) is not the dominant disk
   consumer on this host (`data/` at 8.8G and the repo at 11-12G dwarf it).
2. **When 90 days pass** (around 2026-10-02), re-review: if the source
   projects (`forex-validate`, `smc-test`, `benchmark-bot`,
   `simple-smc-ag-trading-bot`) are confirmed retired with no revival plan,
   those four backups (377M) become safe-to-delete-after-approval, same as
   any other "Archive First" candidate in `CLEANUP_PLAN.md`.
3. **Do not treat `simple-smc-ag-trading-bot_...tar.gz` as disposable just
   because the live directory exists** — a backup's value is in surviving
   the loss of the live copy; delete the backup only after the live directory
   itself is confirmed retired (matching `CLEANUP_PLAN.md`'s existing "Archive
   First" guidance for that repo).
4. Continue verifying `.sha256` checksums before any future restore, and
   before any deletion, per this repo's general evidence-integrity posture.

**No deletion is proposed for immediate execution.** This document is the
policy review only, per this task's constraints.
