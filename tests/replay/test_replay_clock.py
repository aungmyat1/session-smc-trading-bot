from datetime import datetime, timedelta, timezone

import pytest

from replay.replay_clock import ReplayClock


def test_clock_steps_deterministically_and_resets() -> None:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    timestamps = [start + timedelta(minutes=value) for value in (2, 1, 3)]
    clock = ReplayClock(start, start + timedelta(minutes=3), timestamps)

    assert [clock.step(), clock.step(), clock.step()] == sorted(timestamps)
    assert clock.is_finished()
    assert clock.step() is None
    clock.reset()
    assert clock.current_time == start
    assert clock.step() == start + timedelta(minutes=1)


def test_clock_seek_positions_next_step_at_or_after_target() -> None:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    clock = ReplayClock(start, start + timedelta(minutes=5), [start + timedelta(minutes=2), start + timedelta(minutes=4)])

    clock.seek(start + timedelta(minutes=3))
    assert clock.current_time == start + timedelta(minutes=3)
    assert clock.step() == start + timedelta(minutes=4)

    with pytest.raises(ValueError, match="outside"):
        clock.seek(start - timedelta(minutes=1))


def test_clock_preserves_duplicate_candle_timestamps() -> None:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    candle_time = start + timedelta(minutes=1)
    clock = ReplayClock(start, candle_time, [candle_time, candle_time])
    assert clock.step() == candle_time
    assert clock.step() == candle_time
    assert clock.is_finished()
