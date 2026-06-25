# DATA_AUDIT.md
Generated: 2026-06-20 20:58 UTC
Target coverage: ≥ 5.0 years (1825 days)

---
## EUR_USD

### M15
  First bar:  2021-06-21T00:00:00Z
  Last bar:   2026-06-19T20:45:00Z
  Total bars: 121,086
  Coverage:   1824 days

  ✅ Coverage ≥ 4.5yr: 1824d (target: ≥1642d)
  ❌ Missing bars %: 0.916% (target: < 0.1%)
  ✅ Duplicates: 0 (target: 0)
  ✅ Weekend bars: 0 (target: 0 (note: small count ok near DST))
  ✅ Price errors (high<low): 0 (target: 0)
  ✅ Out-of-order bars: 0 (target: 0)
  ❌ **M15 FAIL**

### H1
  First bar:  2021-06-21T00:00:00Z
  Last bar:   2026-06-19T20:00:00Z
  Total bars: 30,274
  Coverage:   1824 days

  ✅ Coverage ≥ 4.5yr: 1824d (target: ≥1642d)
  ❌ Missing bars %: 0.908% (target: < 0.1%)
  ✅ Duplicates: 0 (target: 0)
  ✅ Weekend bars: 0 (target: 0 (note: small count ok near DST))
  ✅ Price errors (high<low): 0 (target: 0)
  ✅ Out-of-order bars: 0 (target: 0)
  ❌ **H1 FAIL**

### H4
  First bar:  2021-06-21T00:00:00Z
  Last bar:   2026-06-19T20:00:00Z
  Total bars: 7,769
  Coverage:   1824 days

  ✅ Coverage ≥ 4.5yr: 1824d (target: ≥1642d)
  ❌ Missing bars %: 0.576% (target: < 0.1%)
  ✅ Duplicates: 0 (target: 0)
  ✅ Weekend bars: 0 (target: 0 (note: small count ok near DST))
  ✅ Price errors (high<low): 0 (target: 0)
  ✅ Out-of-order bars: 0 (target: 0)
  ❌ **H4 FAIL**

---
## GBP_USD

### M15
  First bar:  2023-03-13T00:00:00Z
  Last bar:   2026-06-19T20:45:00Z
  Total bars: 79,339
  Coverage:   1194 days

  ❌ Coverage ≥ 4.5yr: 1194d (target: ≥1642d)
  ❌ Missing bars %: 0.997% (target: < 0.1%)
  ✅ Duplicates: 0 (target: 0)
  ✅ Weekend bars: 0 (target: 0 (note: small count ok near DST))
  ✅ Price errors (high<low): 0 (target: 0)
  ✅ Out-of-order bars: 0 (target: 0)
  ❌ **M15 FAIL**

### H1
  First bar:  2023-03-14T00:00:00Z
  Last bar:   2026-06-19T20:00:00Z
  Total bars: 19,818
  Coverage:   1193 days

  ❌ Coverage ≥ 4.5yr: 1193d (target: ≥1642d)
  ❌ Missing bars %: 0.963% (target: < 0.1%)
  ✅ Duplicates: 0 (target: 0)
  ✅ Weekend bars: 0 (target: 0 (note: small count ok near DST))
  ✅ Price errors (high<low): 0 (target: 0)
  ✅ Out-of-order bars: 0 (target: 0)
  ❌ **H1 FAIL**

### H4
  First bar:  2023-02-01T00:00:00Z
  Last bar:   2026-06-19T20:00:00Z
  Total bars: 5,245
  Coverage:   1234 days

  ❌ Coverage ≥ 4.5yr: 1234d (target: ≥1642d)
  ❌ Missing bars %: 0.7% (target: < 0.1%)
  ✅ Duplicates: 0 (target: 0)
  ✅ Weekend bars: 0 (target: 0 (note: small count ok near DST))
  ✅ Price errors (high<low): 0 (target: 0)
  ✅ Out-of-order bars: 0 (target: 0)
  ❌ **H4 FAIL**

---
## Overall Verdict

**❌ FAILURES — fix data gaps before backtesting**

Gate: missing < 0.1%, duplicates = 0, price errors = 0, coverage ≥ 4.5yr per series.