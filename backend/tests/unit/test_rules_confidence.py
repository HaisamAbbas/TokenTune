from app.services.rules.base import MIN_SAMPLE_SIZE, scaled_confidence


def test_confidence_at_floor_is_low() -> None:
    assert scaled_confidence(MIN_SAMPLE_SIZE) == MIN_SAMPLE_SIZE / (MIN_SAMPLE_SIZE * 4)


def test_confidence_below_floor_is_lower_still() -> None:
    assert scaled_confidence(1) < scaled_confidence(MIN_SAMPLE_SIZE)


def test_confidence_scales_up_with_more_samples() -> None:
    assert scaled_confidence(MIN_SAMPLE_SIZE * 2) > scaled_confidence(MIN_SAMPLE_SIZE)


def test_confidence_caps_at_one() -> None:
    assert scaled_confidence(MIN_SAMPLE_SIZE * 100) == 1.0
