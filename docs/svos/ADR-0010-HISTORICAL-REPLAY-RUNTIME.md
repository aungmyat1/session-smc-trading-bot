# ADR-0010: Historical Replay Runtime Foundation

Date: 2026-07-03
Status: Accepted
Owner: SVOS Strategy Engineering
Scope: System 1 foundation only

## Context

SVOS needs reproducible historical market-data playback for strategy engineering and validation. Replay must eventually feed the same normalized strategy, risk, and execution pathway used by the thin execution bot without copying strategy logic. The first foundation establishes deterministic data playback and evidence generation only.

SVOS has two systems. System 1 is the Strategy Engineering and SVOS validation platform. System 2 is the thin execution bot. Historical Replay belongs exclusively to System 1.

## Decision

The `replay` package provides a deterministic candle clock, historical CSV/Parquet feed, typed configuration, event journal, report, session coordinator, and command-line interface. Candle timestamps are the only clock source. Events use stable sequence numbers and canonical JSON serialization.

Replay preserves provenance by recording the requested symbol, timeframe, time window, data path, strategy package path, and SHA-256 content digests in its evidence. Replay outputs an append-only JSONL event journal, a JSON summary, and a Markdown report under `artifacts/replay/<run_id>/`.

The same candle input, strategy-package content, replay window, symbol, and timeframe must produce the same deterministic replay hash. The run identifier and output location are evidence-routing metadata and do not affect that hash.

## Scope

- Deterministic candle-by-candle stepping.
- CSV input and Parquet input when the project dependency is installed.
- Strict required-field and null validation.
- Ordered market-bar events and reproducible evidence.
- A broker-free self-test.
- A future-safe coordination seam that contains no strategy logic.

## Non-Scope

- Broker connections or broker adapters.
- Live or demo order placement and account-state modification.
- Live authorization or activation.
- Strategy package approval, validation, signing, or promotion.
- Strategy optimization, parameter search, or performance claims.
- Real-time playback speed, asynchronous playback, pause/resume, or dashboard controls.
- Strategy, risk, or order-intent execution in this foundation.

The strategy package path is provenance only in ADR-0010. It is neither loaded nor approved. Until a separately reviewed, side-effect-free System 1 adapter is connected, reports explicitly warn that strategy execution is not connected.

## Safety Boundary

The `replay` package must not import `execution`, `production`, broker clients, runtime authorization, deployment, or approval modules. `ReplaySession` coordinates replay components only and contains no trading strategy or order logic. No environment variable can turn replay into a live-capable runtime.

## Determinism

Input rows are normalized and sorted by UTC timestamp. The clock advances only to known candle timestamps. Event timestamps come from the configured replay window or candle data, never wall-clock time. Canonical event records and provenance digests form the deterministic replay hash.

Changing input candle content, strategy-package content, symbol, timeframe, or replay window changes the hash. Repeating a run with the same values produces the same hash.

## Consequences

System 1 gains auditable market-data playback without acquiring execution authority. Strategy and risk integration remains deliberately deferred. A future ADR or PR may connect a side-effect-free adapter to the shared pathway after its imports and effects are proven safe.

## Validation

The package is validated with replay unit tests, CLI self-test, Ruff, Mypy, and an import-boundary test. A replay result is not evidence of strategy approval, execution readiness, or permission to trade.
