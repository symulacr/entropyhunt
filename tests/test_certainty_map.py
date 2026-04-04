from core.certainty_map import CertaintyMap, shannon_entropy


def test_entropy_peaks_at_half_certainty() -> None:
    assert shannon_entropy(0.5) > shannon_entropy(0.8)
    assert shannon_entropy(0.5) == 1.0


def test_decay_moves_certainty_toward_half() -> None:
    certainty_map = CertaintyMap(2, initial_certainty=0.5, decay_rate=0.01)
    certainty_map.set_certainty((0, 0), 0.9, updated_by="test", now_ms=0)
    certainty_map.decay_all(seconds=10, now_ms=10_000)
    assert certainty_map.cell((0, 0)).certainty < 0.9
    assert certainty_map.cell((0, 0)).certainty > 0.5
