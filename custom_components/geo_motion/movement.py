"""Pure GPS sample history and movement calculation for GeoMotion."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta

from homeassistant.util import location as location_util

from .const import MAX_HISTORY_SAMPLES, MIN_SAMPLE_SPACING_SECONDS


@dataclass(slots=True, frozen=True)
class GPSSample:
    timestamp: datetime
    latitude: float
    longitude: float
    accuracy: float | None


@dataclass(slots=True, frozen=True)
class MovementEvaluation:
    is_moving: bool | None
    reason: str
    current: GPSSample | None
    reference: GPSSample | None
    reference_age: float | None
    displacement_m: float | None
    effective_threshold_m: float | None
    sample_count: int
    last_meaningful_movement: datetime | None


class GPSHistory:
    """Keep a small in-memory sample window and evaluate movement."""

    def __init__(
        self,
        history_window: int,
        comparison_age: int,
        min_reference_age: int,
        min_distance_m: float,
        default_accuracy: float,
        stationary_timeout: int,
    ) -> None:
        self.history_window = history_window
        self.comparison_age = min(comparison_age, history_window)
        self.min_reference_age = min(min_reference_age, self.comparison_age)
        self.min_distance_m = min_distance_m
        self.default_accuracy = default_accuracy
        self.stationary_timeout = stationary_timeout
        self.samples: deque[GPSSample] = deque(maxlen=MAX_HISTORY_SAMPLES)
        self.last_meaningful_movement: datetime | None = None
        self.last_reliable_state: bool | None = None

    def add_sample(self, sample: GPSSample) -> None:
        if self.samples and sample.timestamp < self.samples[-1].timestamp:
            ordered = sorted([*self.samples, sample], key=lambda item: item.timestamp)
            self.samples = deque(ordered[-MAX_HISTORY_SAMPLES:], maxlen=MAX_HISTORY_SAMPLES)
            self.prune(self.samples[-1].timestamp)
            return
        if self.samples and (
            sample.timestamp - self.samples[-1].timestamp
        ).total_seconds() < MIN_SAMPLE_SPACING_SECONDS:
            self.samples[-1] = sample
        else:
            self.samples.append(sample)
        self.prune(sample.timestamp)

    def prune(self, now: datetime) -> None:
        cutoff = now - timedelta(seconds=self.history_window)
        while self.samples and self.samples[0].timestamp < cutoff:
            self.samples.popleft()

    def evaluate(self, *, now: datetime | None = None) -> MovementEvaluation:
        if not self.samples:
            return self._result(None, "insufficient_history")
        now = now or self.samples[-1].timestamp
        self.prune(now)
        if not self.samples:
            return self._result(None, "stale_history")

        current = self.samples[-1]
        candidates = []
        for sample in self.samples:
            if sample is current:
                continue
            age = (current.timestamp - sample.timestamp).total_seconds()
            if self.min_reference_age <= age <= self.history_window:
                candidates.append((age, sample))

        if not candidates:
            if self.last_reliable_state is not None:
                return self._result(
                    self.last_reliable_state,
                    "holding_previous_state",
                    current=current,
                )
            return self._result(None, "insufficient_history", current=current)

        reference_age, reference = min(
            candidates, key=lambda item: abs(item[0] - self.comparison_age)
        )
        displacement = location_util.distance(
            current.latitude,
            current.longitude,
            reference.latitude,
            reference.longitude,
        )
        if displacement is None:
            return self._result(
                None,
                "distance_unavailable",
                current=current,
                reference=reference,
                reference_age=reference_age,
            )

        current_accuracy = (
            current.accuracy if current.accuracy is not None else self.default_accuracy
        )
        reference_accuracy = (
            reference.accuracy if reference.accuracy is not None else self.default_accuracy
        )
        threshold = max(self.min_distance_m, current_accuracy + reference_accuracy)

        if displacement > threshold:
            self.last_meaningful_movement = current.timestamp
            self.last_reliable_state = True
            reason = "moving"
            state = True
        elif (
            self.last_meaningful_movement is not None
            and (current.timestamp - self.last_meaningful_movement).total_seconds()
            <= self.stationary_timeout
        ):
            self.last_reliable_state = True
            reason = "stationary_hold"
            state = True
        else:
            self.last_reliable_state = False
            reason = "stationary"
            state = False

        return self._result(
            state,
            reason,
            current=current,
            reference=reference,
            reference_age=reference_age,
            displacement=displacement,
            threshold=threshold,
        )

    def _result(
        self,
        state: bool | None,
        reason: str,
        *,
        current: GPSSample | None = None,
        reference: GPSSample | None = None,
        reference_age: float | None = None,
        displacement: float | None = None,
        threshold: float | None = None,
    ) -> MovementEvaluation:
        return MovementEvaluation(
            state,
            reason,
            current,
            reference,
            reference_age,
            displacement,
            threshold,
            len(self.samples),
            self.last_meaningful_movement,
        )
