"""
strategy_generator.py
Generates a population of strategies from the parameter grid.
"""

import itertools
import json
from pathlib import Path
from .parameter_grid import PARAMETERS

EXPERIMENTS_DIR = Path("research_db/experiments")
EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)


def generate_strategies():
    """Create all possible strategy combinations."""
    keys = list(PARAMETERS.keys())
    values = [PARAMETERS[k] for k in keys]

    strategies = []
    strategy_id = 1

    for combo in itertools.product(*values):
        strategy = dict(zip(keys, combo))
        strategy["strategy_id"] = f"STRAT_{strategy_id:04d}"
        strategy["name"] = (
            f"{strategy['session']}_Sweep{strategy['require_sweep']}_"
            f"OB{strategy['require_ob']}_FVG{strategy['require_fvg']}_"
            f"{strategy['direction_filter']}_RR{strategy['rr_multiple']}"
        )
        strategies.append(strategy)
        strategy_id += 1

    # Save registry
    registry_path = EXPERIMENTS_DIR / "strategy_registry.json"
    with open(registry_path, "w") as f:
        json.dump(strategies, f, indent=2)

    print(f"Generated {len(strategies)} strategies")
    print(f"Registry saved to {registry_path}")
    return strategies


if __name__ == "__main__":
    generate_strategies()
