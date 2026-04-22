
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.certainty import Coordinate

@dataclass(slots=True)
class MilestoneScheduler:

    contention_deadline_s: int = 30
    failure_at_s: int = 60
    reclaim_force_at_s: int = 75
    target_unlock_at_s: int = 90
    target_force_at_s: int = 110
    survivor_deadline_s: int = 150
    contention_cell: Coordinate | None = None
    contention_complete: bool = False
    failure_logged: bool = False
    released_cell: Coordinate | None = None
    release_time_s: int | None = None
    reclaimed_time_s: int | None = None
    target_priority_armed: bool = False
