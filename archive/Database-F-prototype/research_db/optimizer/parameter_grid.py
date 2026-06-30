"""
parameter_grid.py
Defines the hyperparameter space for strategy generation.
"""

PARAMETERS = {
    "session": ["London", "NewYork", "Both", "Any"],
    "require_sweep": [True, False],
    "require_ob": [True, False],
    "require_fvg": [True, False],
    "direction_filter": ["LONG", "SHORT", "ALL"],
    "rr_multiple": [1.5, 2.0, 2.5, 3.0],
}
