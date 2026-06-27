# D2E3

## Overview

D2E3 is a standalone stateful PDH/PDL sweep plus MSS research branch. It is implemented in `strategy/d2_e3/signal_engine.py` and executed through `scripts/run_d2_e3_demo.py`.

## Audit Status

- Catalog status: `research`
- Approval: `false`
- Version: `0.1`
- Deployment target: `research`
- Runtime path: standalone demo/research runner

## Runtime Behavior

- The engine keeps per-symbol state across polls.
- It emits setup, confirmation, fill, close, and expiry events.
- It is not wired into `scripts/run_portfolio.py`.
- It uses its own `Signal` dataclass, not `core.Signal`.

