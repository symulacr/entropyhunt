from simulation.peer_protocol import (
    bft_round_topic,
    heartbeat_topic,
    make_bft_round_payload,
    make_claim_payload,
    parse_bft_round_payload,
    parse_claim_payload,
    parse_peer_endpoint,
)


def test_parse_peer_endpoint_supports_optional_peer_id() -> None:
    endpoint = parse_peer_endpoint("drone_2@127.0.0.1:9102")
    assert endpoint.peer_id == "drone_2"
    assert endpoint.host == "127.0.0.1"
    assert endpoint.port == 9102

    without_id = parse_peer_endpoint("127.0.0.1:9103")
    assert without_id.peer_id is None
    assert without_id.port == 9103


def test_claim_and_bft_payload_helpers_round_trip_coordinates() -> None:
    claim = parse_claim_payload(
        make_claim_payload(
            claim_id="claim-1",
            drone_id="drone_1",
            cell=(1, 2),
            position=(0, 0),
            timestamp_ms=100,
        )
    )
    assert claim.cell == (1, 2)
    assert heartbeat_topic("drone_1") == "swarm/heartbeat/drone_1"

    payload = parse_bft_round_payload(
        make_bft_round_payload(
            round_id=3,
            cell=(1, 2),
            assignments=[{"drone_id": "drone_1", "cell": [1, 2], "reason": "winner", "subzone": None}],
            rationale="single-claim quorum",
        )
    )
    assert payload.round_id == 3
    assert payload.cell == (1, 2)
    assert payload.assignments[0].drone_id == "drone_1"
    assert bft_round_topic(3) == "swarm/bft_result/3"
