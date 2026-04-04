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
    def select_next_zone(
        self,
        certainty_map: CertaintyMap,
        *,
        claimed_zones: set[Coordinate],
        current_position: Coordinate,
    ) -> ZoneSelection | None:
        ranked = certainty_map.ranked_cells(claimed_zones)
        if not ranked:
            return None

        best = sorted(
            (
                ZoneSelection(
                    coordinate=score.coordinate,
                    certainty=score.certainty,
                    entropy=score.entropy,
                    distance=dist(current_position, score.coordinate),
                )
                for score in ranked
            ),
            key=lambda item: (-item.entropy, item.distance, item.coordinate[1], item.coordinate[0]),
        )
        return best[0]

    def top_candidates(
        self,
        certainty_map: CertaintyMap,
        *,
        claimed_zones: set[Coordinate],
        current_position: Coordinate,
        limit: int = 3,
    ) -> list[ZoneSelection]:
        ranked = certainty_map.ranked_cells(claimed_zones)
        selections = [
            ZoneSelection(
                coordinate=score.coordinate,
                certainty=score.certainty,
                entropy=score.entropy,
                distance=dist(current_position, score.coordinate),
            )
            for score in ranked
        ]
        return sorted(
            selections,
            key=lambda item: (-item.entropy, item.distance, item.coordinate[1], item.coordinate[0]),
        )[:limit]
