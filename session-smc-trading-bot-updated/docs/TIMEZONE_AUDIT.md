# TIMEZONE_AUDIT.md
# Session Trading Bot — Timezone Reference and DST Verification
# v1.0 | referenced by session_builder.py + classify_session()

---

## §1 — Offset Table

| Abbreviation | Full Name | UTC Offset | Active period (US) |
|---|---|---|---|
| EST | Eastern Standard Time | UTC − 5 | Nov first-Sun → Mar second-Sun |
| EDT | Eastern Daylight Time | UTC − 4 | Mar second-Sun → Nov first-Sun |

**2024 DST transitions (US):**
- Spring forward: **2024-03-10** at 02:00 EST → 03:00 EDT (clocks advance 1 hour)
- Fall back:      **2024-11-03** at 02:00 EDT → 01:00 EST (clocks recede 1 hour)

The codebase uses `zoneinfo.ZoneInfo("America/New_York")` for all EST/EDT conversions.
This handles all DST transitions automatically — no manual offset arithmetic anywhere.

---

## §2 — Session Window Definitions (in EST/EDT local time)

All sessions are defined in local New York time. UTC equivalents shift by ±1 hour
when DST transitions occur.

| Session | Local (EST/EDT) | UTC in EST | UTC in EDT |
|---|---|---|---|
| Asian Build | 18:00 prev day → 02:00 | 23:00 prev UTC → 07:00 UTC | 22:00 prev UTC → 06:00 UTC |
| London Killzone | 02:00 → 05:00 | 07:00 → 10:00 UTC | 06:00 → 09:00 UTC |
| New York Killzone | 07:00 → 10:00 | 12:00 → 15:00 UTC | 11:00 → 14:00 UTC |

**Boundary convention (all windows):**
- Start is **inclusive**: a bar opening exactly at the start time is inside the window.
- End is **exclusive**: a bar opening exactly at the end time is outside the window.

This matches the `classify_session()` implementation:
```python
if 2 <= h < 5: return "london"    # hours [2, 3, 4] in EST/EDT
if 7 <= h < 10: return "new_york" # hours [7, 8, 9] in EST/EDT
```

---

## §3 — Example: 2024-01-15 (EST, UTC − 5)

January is always in EST. No DST ambiguity.

### Asian Session (building the range for trade date 2024-01-15)

| Boundary | EST | UTC |
|---|---|---|
| Session open | 2024-01-14 18:00 EST | 2024-01-14 **23:00** UTC |
| Session close (excluded) | 2024-01-15 02:00 EST | 2024-01-15 **07:00** UTC |

M15 bars included: `2024-01-14T23:00Z` through `2024-01-15T06:45Z` (inclusive).
Bar at `2024-01-15T07:00Z` = 02:00 EST → belongs to London, excluded from Asian range.

### London Killzone (2024-01-15)

| Boundary | EST | UTC |
|---|---|---|
| Open (inclusive) | 2024-01-15 02:00 EST | 2024-01-15 **07:00** UTC |
| Close (exclusive) | 2024-01-15 05:00 EST | 2024-01-15 **10:00** UTC |

Scannable M15 bars: `07:00`, `07:15`, …, `09:45` UTC.
Bar at `10:00 UTC` = 05:00 EST → outside window, not scanned.

### New York Killzone (2024-01-15)

| Boundary | EST | UTC |
|---|---|---|
| Open (inclusive) | 2024-01-15 07:00 EST | 2024-01-15 **12:00** UTC |
| Close (exclusive) | 2024-01-15 10:00 EST | 2024-01-15 **15:00** UTC |

Scannable M15 bars: `12:00`, `12:15`, …, `14:45` UTC.

### Timeline summary (2024-01-15, EST)

```
UTC  00:00               07:00           10:00   12:00           15:00     23:00
     |                   |               |       |               |         |
     [══ Asian build ════]               |       |               |
                         [═ London KZ ══]       [══ NY KZ ══════]
     ← 2024-01-14 23:00                                                   ← next Asian
```

---

## §4 — Example: 2024-07-15 (EDT, UTC − 4)

July is always in EDT. UTC offsets shift by +1 hour relative to EST.

### Asian Session (building the range for trade date 2024-07-15)

| Boundary | EDT | UTC |
|---|---|---|
| Session open | 2024-07-14 18:00 EDT | 2024-07-14 **22:00** UTC |
| Session close (excluded) | 2024-07-15 02:00 EDT | 2024-07-15 **06:00** UTC |

M15 bars included: `2024-07-14T22:00Z` through `2024-07-15T05:45Z` (inclusive).
Bar at `2024-07-15T06:00Z` = 02:00 EDT → belongs to London, excluded from Asian range.

### London Killzone (2024-07-15)

| Boundary | EDT | UTC |
|---|---|---|
| Open (inclusive) | 2024-07-15 02:00 EDT | 2024-07-15 **06:00** UTC |
| Close (exclusive) | 2024-07-15 05:00 EDT | 2024-07-15 **09:00** UTC |

Scannable M15 bars: `06:00`, `06:15`, …, `08:45` UTC.

### New York Killzone (2024-07-15)

| Boundary | EDT | UTC |
|---|---|---|
| Open (inclusive) | 2024-07-15 07:00 EDT | 2024-07-15 **11:00** UTC |
| Close (exclusive) | 2024-07-15 10:00 EDT | 2024-07-15 **14:00** UTC |

Scannable M15 bars: `11:00`, `11:15`, …, `13:45` UTC.

### Timeline summary (2024-07-15, EDT)

```
UTC  00:00           06:00       09:00   11:00           14:00     22:00
     |               |           |       |               |         |
     [═ Asian build ═]           |       |               |
                     [═ London ══]       [════ NY KZ ════]
     ← 2024-07-14 22:00                                           ← next Asian
```

---

## §5 — EST vs EDT Comparison

| Session boundary | EST (UTC−5) | EDT (UTC−4) | Δ |
|---|---|---|---|
| Asian open (UTC) | prev 23:00 | prev 22:00 | −1h |
| Asian close (UTC) | 07:00 | 06:00 | −1h |
| London open (UTC) | 07:00 | 06:00 | −1h |
| London close (UTC) | 10:00 | 09:00 | −1h |
| NY open (UTC) | 12:00 | 11:00 | −1h |
| NY close (UTC) | 15:00 | 14:00 | −1h |

All windows shift exactly 1 hour earlier in UTC during summer (EDT).
Local session times never change — only the UTC representation shifts.

---

## §6 — DST Transition Edge Cases

### Spring-forward day: 2024-03-10

At 02:00 EST the clock jumps to 03:00 EDT. There is no 02:30 EST on this day.

**Asian session for trade date 2024-03-10:**
- Start: 2024-03-09T23:00Z (18:00 EST, pre-transition)
- End:   2024-03-10T06:00Z (02:00 EDT, post-transition — note: already EDT)

The `zoneinfo` library handles this automatically. There is NO ambiguity for the Asian
end boundary: 06:00 UTC on the transition day is 02:00 EDT, which is after the clock
has already sprung forward.

**London Killzone for 2024-03-10:**
- 02:00 local = 06:00 UTC (EDT already active)
- 05:00 local = 09:00 UTC

**Effect on data collection:** on the spring-forward day, one M15 bar is permanently
missing (the 02:15–02:30 EST slot that never existed). The `build_asian_range` minimum-
bar gate (< 4 bars → skip) catches degenerate Asian sessions from holidays or short
pre-transition nights.

### Fall-back day: 2024-11-03

At 02:00 EDT the clock falls back to 01:00 EST. The interval 01:00–02:00 local time
repeats once.

**Asian session for trade date 2024-11-03:**
- Start: 2024-11-02T22:00Z (18:00 EDT, pre-transition)
- End:   2024-11-03T07:00Z (02:00 EST, post-transition)

The `zoneinfo` library disambiguates the repeated hour via the `fold` attribute.
`classify_session()` reads the resulting integer hour, so duplicate bars at the same
local hour are both scanned but the sweep/displacement logic is idempotent.

---

## §7 — Code Verification

### `classify_session()` logic (session_builder.py)

```python
def classify_session(dt_utc: datetime) -> str | None:
    h = _to_est(_parse_utc(dt_utc)).hour
    if 2 <= h < 5: return "london"
    if 7 <= h < 10: return "new_york"
    return None
```

`_to_est` converts to `America/New_York`, which is EST in winter and EDT in summer.
The integer `.hour` is always in local time, so the bounds `[2, 5)` and `[7, 10)` are
timezone-stable. The UTC equivalent of those bounds shifts automatically with DST.

### `build_asian_range()` logic (session_builder.py)

```python
if (c_date == prev_day and c_hour >= 18) or (c_date == trade_date and c_hour < 2):
```

`c_date` and `c_hour` are derived from `t_est = _to_est(bar_time_utc)`. So:
- `c_hour >= 18`: selects 18:00–23:59 EST/EDT on the previous calendar day
- `c_hour < 2`: selects 00:00–01:59 EST/EDT on the trade date

Both sides use the same local-time representation, so they correctly span the overnight
window regardless of whether it's EST or EDT.

### VALIDATION-01 cross-check (2023-03-14 — post-spring-forward, EDT)

2023 DST spring-forward: 2023-03-12. So 2023-03-14 is already in EDT (UTC−4).

Observed session bars in `docs/DRY_RUN_2023_03_14.md`:
- London bars: `06:00`–`08:45` UTC → 02:00–04:45 EDT ✅ (inside [02:00, 05:00))
- NY bars: `11:00`–`13:45` UTC → 07:00–09:45 EDT ✅ (inside [07:00, 10:00))

The 1-hour EDT shift (vs EST 07:00/12:00 open) was applied automatically. ✅

---

## §8 — Implementation Checklist

| Requirement | Implementation | Status |
|---|---|---|
| EST/EDT auto-switching | `zoneinfo.ZoneInfo("America/New_York")` | ✅ |
| Asian session uses local calendar date | `t_est.date()`, `t_est.hour` | ✅ |
| Midnight crossing handled | `prev_day = trade_date - timedelta(days=1)` | ✅ |
| Killzone uses local hour | `classify_session` reads `.hour` from EST/EDT dt | ✅ |
| No manual UTC offset arithmetic | No `timedelta(hours=-5)` in codebase | ✅ |
| Spring-forward short session caught | `< 4 bars` gate in `build_asian_range` | ✅ |
