from __future__ import annotations

from dataclasses import dataclass
from math import dist, isclose

from core.certainty_map import CertaintyMap, Coordinate
from core.zone_selector import ZoneSelector


@dataclass(frozen=True, slots=True)
class ClaimRequest:
    claim_id: str
    drone_id: str
    cell: Coordinate
    position: Coordinate
    timestamp_ms: int


@dataclass(frozen=True, slots=True)
class ZoneAssignment:
    drone_id: str
    cell: Coordinate
    reason: str
    subzone: str | None = None


@dataclass(frozen=True, slots=True)
class AuctionDecision:
    cell: Coordinate
    assignments: tuple[ZoneAssignment, ...]
    rationale: str


def _fallback_assignments(
    losers: list[ClaimRequest],
    *,
    certainty_map: CertaintyMap,
    selector: ZoneSelector,
    claimed_zones: set[Coordinate],
) -> list[ZoneAssignment]:
    assignments: list[ZoneAssignment] = []
    reserved = set(claimed_zones)
    for loser in losers:
        selection = selector.select_next_zone(
            certainty_map,
            claimed_zones=reserved,
            current_position=loser.position,
        )
        if selection is None:
            assignments.append(ZoneAssignment(drone_id=loser.drone_id, cell=loser.cell, reason="idle"))
            continue
        reserved.add(selection.coordinate)
        assignments.append(
            ZoneAssignment(
                drone_id=loser.drone_id,
                cell=selection.coordinate,
                reason="fallback",
            )
        )
    return assignments


def resolve_conflict(
    claims: list[ClaimRequest],
    *,
    certainty_map: CertaintyMap,
    selector: ZoneSelector,
    claimed_zones: set[Coordinate],
) -> AuctionDecision:
    assert claims, "resolve_conflict requires at least one claim"
    cell = claims[0].cell
    if len(claims) == 1:
        claim = claims[0]
        return AuctionDecision(
            cell=cell,
            assignments=(ZoneAssignment(drone_id=claim.drone_id, cell=cell, reason="winner"),),
            rationale="single-claim quorum",
        )

    ranked = sorted(
        claims,
        key=lambda claim: (claim.timestamp_ms, dist(claim.position, claim.cell), claim.drone_id),
    )
    winner = ranked[0]
    runner_up = ranked[1]
    winner_distance = dist(winner.position, cell)
    runner_up_distance = dist(runner_up.position, cell)

    if winner.timestamp_ms == runner_up.timestamp_ms and isclose(winner_distance, runner_up_distance):
        split_assignments = [
            ZoneAssignment(drone_id=winner.drone_id, cell=cell, reason="split", subzone="left"),
            ZoneAssignment(drone_id=runner_up.drone_id, cell=cell, reason="split", subzone="right"),
        ]
        fallback = _fallback_assignments(
            ranked[2:],
            certainty_map=certainty_map,
            selector=selector,
            claimed_zones=claimed_zones | {cell},
        )
        return AuctionDecision(
            cell=cell,
            assignments=tuple(split_assignments + fallback),
            rationale="distance tie -> split zone",
        )

    fallback = _fallback_assignments(
        ranked[1:],
        certainty_map=certainty_map,
        selector=selector,
        claimed_zones=claimed_zones | {cell},
    )
    return AuctionDecision(
        cell=cell,
        assignments=(ZoneAssignment(drone_id=winner.drone_id, cell=cell, reason="winner"), *fallback),
        rationale="timestamp precedence + proximity tiebreak",
    )
