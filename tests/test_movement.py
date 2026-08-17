from datetime import UTC, datetime, timedelta

from custom_components.geo_motion.movement import GPSSample, GPSHistory


def _history() -> GPSHistory:
    return GPSHistory(600, 300, 60, 20, 25, 120)


def test_insufficient_history() -> None:
    history = _history()
    now = datetime(2026, 1, 1, tzinfo=UTC)
    history.add_sample(GPSSample(now, 55.0, 12.0, 10))
    result = history.evaluate(now=now)
    assert result.is_moving is None
    assert result.reason == "insufficient_history"


def test_stationary_with_gps_drift() -> None:
    history = _history()
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    history.add_sample(GPSSample(now - timedelta(minutes=5), 55.0, 12.0, 15))
    history.add_sample(GPSSample(now, 55.0001, 12.0001, 15))
    result = history.evaluate(now=now)
    assert result.is_moving is False
    assert result.reason == "stationary"


def test_meaningful_movement() -> None:
    history = _history()
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    history.add_sample(GPSSample(now - timedelta(minutes=5), 55.0, 12.0, 5))
    history.add_sample(GPSSample(now, 55.003, 12.0, 5))
    result = history.evaluate(now=now)
    assert result.is_moving is True
    assert result.reason == "moving"


def test_holds_reliable_state_through_reference_gap() -> None:
    history = _history()
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    history.add_sample(GPSSample(now - timedelta(minutes=5), 55.0, 12.0, 5))
    history.add_sample(GPSSample(now, 55.0, 12.0, 5))
    assert history.evaluate(now=now).is_moving is False
    history.samples.clear()
    history.add_sample(GPSSample(now + timedelta(seconds=30), 55.0, 12.0, 5))
    result = history.evaluate(now=now + timedelta(seconds=30))
    assert result.is_moving is False
    assert result.reason == "holding_previous_state"


def test_holds_stationary_state_when_history_becomes_stale() -> None:
    history = _history()
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    history.add_sample(GPSSample(now - timedelta(minutes=5), 55.0, 12.0, 5))
    history.add_sample(GPSSample(now, 55.0, 12.0, 5))
    assert history.evaluate(now=now).is_moving is False

    later = now + timedelta(minutes=11)
    result = history.evaluate(now=later)
    assert result.is_moving is False
    assert result.reason == "holding_stale_state"


def test_holds_moving_state_when_history_becomes_stale() -> None:
    history = _history()
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    history.add_sample(GPSSample(now - timedelta(minutes=5), 55.0, 12.0, 5))
    history.add_sample(GPSSample(now, 55.003, 12.0, 5))
    assert history.evaluate(now=now).is_moving is True

    later = now + timedelta(minutes=11)
    result = history.evaluate(now=later)
    assert result.is_moving is True
    assert result.reason == "holding_stale_state"
