from app.services.rules.base import (
    CONFIDENCE_HIGH_THRESHOLD,
    CONFIDENCE_MEDIUM_THRESHOLD,
    MIN_SAMPLE_SIZE,
    bucket_confidence,
    scaled_confidence,
)


def test_confidence_at_floor_is_low() -> None:
    assert scaled_confidence(MIN_SAMPLE_SIZE) == MIN_SAMPLE_SIZE / (MIN_SAMPLE_SIZE * 4)


def test_confidence_below_floor_is_lower_still() -> None:
    assert scaled_confidence(1) < scaled_confidence(MIN_SAMPLE_SIZE)


def test_confidence_scales_up_with_more_samples() -> None:
    assert scaled_confidence(MIN_SAMPLE_SIZE * 2) > scaled_confidence(MIN_SAMPLE_SIZE)


def test_confidence_caps_at_one() -> None:
    assert scaled_confidence(MIN_SAMPLE_SIZE * 100) == 1.0


def test_bucket_confidence_high() -> None:
    assert bucket_confidence(CONFIDENCE_HIGH_THRESHOLD) == "high"
    assert bucket_confidence(1.0) == "high"


def test_bucket_confidence_medium() -> None:
    assert bucket_confidence(CONFIDENCE_MEDIUM_THRESHOLD) == "medium"
    assert bucket_confidence(CONFIDENCE_HIGH_THRESHOLD - 0.01) == "medium"


def test_bucket_confidence_low() -> None:
    assert bucket_confidence(0.0) == "low"
    assert bucket_confidence(CONFIDENCE_MEDIUM_THRESHOLD - 0.01) == "low"
