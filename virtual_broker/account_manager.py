from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AccountManager:
    """Simple execution account state for virtual broker runs."""

    balance: float = 10_000.0
    equity: float = 10_000.0
    margin: float = 0.0
    free_margin: float = 10_000.0
    daily_loss: float = 0.0
    open_risk: float = 0.0
    metadata: dict = field(default_factory=dict)

    def update_equity(self, equity: float) -> None:
        self.equity = equity
        self.free_margin = max(self.balance - self.margin, 0.0)

    def apply_margin(self, margin: float) -> None:
        self.margin = margin
        self.free_margin = max(self.balance - margin, 0.0)

