from auction.protocol import ClaimRequest
from core.bft import BftCoordinator
from core.certainty_map import CertaintyMap
from core.zone_selector import ZoneSelector


def test_bft_prefers_closest_drone_on_timestamp_tie() -> None:
    bft = BftCoordinator(["drone_1", "drone_2", "drone_3"])
    certainty_map = CertaintyMap(4)
    claims = [
        ClaimRequest("c1", "drone_1", (1, 1), (0, 0), 1_000),
        ClaimRequest("c2", "drone_2", (1, 1), (1, 0), 1_000),
    ]
    result = bft.resolve_claims(
        claims,
        certainty_map=certainty_map,
        selector=ZoneSelector(),
        claimed_zones=set(),
    )
    assert result.assignments[0].drone_id == "drone_2"
    assert len(result.votes) == 3


def test_bft_splits_zone_on_exact_tie() -> None:
    bft = BftCoordinator(["drone_1", "drone_2", "drone_3"])
    certainty_map = CertaintyMap(4)
    claims = [
        ClaimRequest("c1", "drone_1", (1, 1), (0, 1), 1_000),
        ClaimRequest("c2", "drone_2", (1, 1), (2, 1), 1_000),
    ]
    result = bft.resolve_claims(
        claims,
        certainty_map=certainty_map,
        selector=ZoneSelector(),
        claimed_zones=set(),
    )
    assert {assignment.subzone for assignment in result.assignments[:2]} == {"left", "right"}


def test_bft_is_deterministic_for_repeated_same_contention() -> None:
    winners: list[str] = []
    for _ in range(10):
        bft = BftCoordinator(["drone_1", "drone_2", "drone_3"])
        result = bft.resolve_claims(
            [
                ClaimRequest("c1", "drone_1", (1, 1), (0, 0), 1_000),
                ClaimRequest("c2", "drone_2", (1, 1), (1, 0), 1_000),
            ],
            certainty_map=CertaintyMap(4),
            selector=ZoneSelector(),
            claimed_zones=set(),
        )
        winners.append(result.assignments[0].drone_id)
    assert winners == ["drone_2"] * 10
