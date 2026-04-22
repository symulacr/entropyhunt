
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.certainty import Coordinate

@dataclass(frozen=True, slots=True, kw_only=True)
class BaseSimulationConfig:

    grid: int = 10
    duration: int = 180
    tick_seconds: int = 1
    search_increment: float = 0.05
    completion_certainty: float = 0.95
    decay_rate: float = 0.001
    stale_after_seconds: int = 3
    target: Coordinate = (7, 3)
    stop_on_survivor: bool = False
    proofs_path: str = "proofs.jsonl"
