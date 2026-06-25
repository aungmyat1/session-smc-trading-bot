"""
Strategy A — Session Liquidity Reversal.

Signal chain (10 phases, AND-gated):
  1  Asian session range build   (18:00–02:00 EST)
  2  4H HTF bias filter          (HH+HL bullish | LL+LH bearish)
  3  Killzone filter             (London 02–05 EST | NY 07–10 EST)
  4  Asian range minimum filter  (EURUSD ≥ 15pip | GBPUSD ≥ 20pip)
  5  Liquidity sweep             (pierce Asian H/L, close back inside)
  6  Displacement confirmation   (|body| > 1.2×ATR, close in 25% zone)
  7  Signal construction         (entry=close, SL=sweep extreme±buffer, TP=RR×SL)

Entry: bar-close of displacement candle.
One trade per session per day.

Modules are built incrementally (SA-01 through SA-07).
See docs/TASK_QUEUE.md for the build sequence.
"""
