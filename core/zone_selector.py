from __future__ import annotations

from dataclasses import dataclass
from math import dist

from core.certainty_map import CertaintyMap, Coordinate


@dataclass(frozen=True, slots=True)
class ZoneSelection:
    coordinate: Coordinate
    certainty: float
    entropy: float
    distance: float


class ZoneSelector:
    def _selections(
        self,
        certainty_map: CertaintyMap,
        *,
        claimed_zones: set[Coordinate],
        current_position: Coordinate,
        blocked_zones: set[Coordinate] | None = None,
    ) -> list[ZoneSelection]:
        blocked = blocked_zones or set()
        return [
            ZoneSelection(
                coordinate=score.coordinate,
                certainty=score.certainty,
                entropy=score.entropy,
                distance=dist(current_position, score.coordinate),
            )
            for score in certainty_map.ranked_cells(claimed_zones | blocked)
        ]

    def select_next_zone(
        self,
        certainty_map: CertaintyMap,
        *,
        claimed_zones: set[Coordinate],
        current_position: Coordinate,
        blocked_zones: set[Coordinate] | None = None,
    ) -> ZoneSelection | None:
        """Returns argmax H(cell) over unclaimed cells not in exclude_set. H = Shannon entropy of certainty value."""
        selections = self._selections(
            certainty_map,
            claimed_zones=claimed_zones,
            current_position=current_position,
            blocked_zones=blocked_zones,
        )
        if not selections:
            return None
        return min(
            selections,
            key=lambda item: (-item.entropy, item.distance, item.coordinate[1], item.coordinate[0]),
        )

    def top_candidates(
        self,
        certainty_map: CertaintyMap,
        *,
        claimed_zones: set[Coordinate],
        current_position: Coordinate,
        limit: int = 3,
        blocked_zones: set[Coordinate] | None = None,
    ) -> list[ZoneSelection]:
        selections = self._selections(
            certainty_map,
            claimed_zones=claimed_zones,
            current_position=current_position,
            blocked_zones=blocked_zones,
        )
        return sorted(
            selections,
            key=lambda item: (-item.entropy, item.distance, item.coordinate[1], item.coordinate[0]),
        )[:limit]
