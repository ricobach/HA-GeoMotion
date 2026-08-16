"""Home Assistant coordinator for GeoMotion."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
import time

from homeassistant.components.recorder import get_instance, history
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_GPS_ACCURACY, ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_COMPARISON_AGE,
    CONF_DEFAULT_ACCURACY,
    CONF_HISTORY_WINDOW,
    CONF_MIN_DISTANCE_M,
    CONF_MIN_REFERENCE_AGE,
    CONF_SOURCE_ENTITY,
    CONF_STATIONARY_TIMEOUT,
    DEFAULT_COMPARISON_AGE,
    DEFAULT_DEFAULT_ACCURACY,
    DEFAULT_HISTORY_WINDOW,
    DEFAULT_MIN_DISTANCE_M,
    DEFAULT_MIN_REFERENCE_AGE,
    DEFAULT_STATIONARY_TIMEOUT,
    DOMAIN,
    ENTITY_REFRESH_INTERVAL,
    SUBENTRY_TYPE_TRACKED_ENTITY,
)
from .movement import GPSSample, GPSHistory, MovementEvaluation

_LOGGER = logging.getLogger(__name__)


def sample_from_state(state: State) -> GPSSample | None:
    latitude = state.attributes.get(ATTR_LATITUDE)
    longitude = state.attributes.get(ATTR_LONGITUDE)
    if latitude is None or longitude is None:
        return None
    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError):
        return None
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        return None

    accuracy: float | None = None
    raw_accuracy = state.attributes.get(ATTR_GPS_ACCURACY)
    if raw_accuracy is not None:
        try:
            parsed = float(raw_accuracy)
        except (TypeError, ValueError):
            pass
        else:
            if parsed >= 0:
                accuracy = parsed

    return GPSSample(state.last_updated, lat, lon, accuracy)


class MovementCoordinator(DataUpdateCoordinator[dict[str, MovementEvaluation]]):
    """Maintain live movement histories for configured source entities."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.histories: dict[str, GPSHistory] = {}
        self._last_publish = 0.0
        self._max_history_window = DEFAULT_HISTORY_WINDOW

        for subentry in entry.subentries.values():
            if subentry.subentry_type != SUBENTRY_TYPE_TRACKED_ENTITY:
                continue
            data = subentry.data
            source = data[CONF_SOURCE_ENTITY]
            window = int(data.get(CONF_HISTORY_WINDOW, DEFAULT_HISTORY_WINDOW))
            self._max_history_window = max(self._max_history_window, window)
            self.histories[source] = GPSHistory(
                window,
                int(data.get(CONF_COMPARISON_AGE, DEFAULT_COMPARISON_AGE)),
                int(data.get(CONF_MIN_REFERENCE_AGE, DEFAULT_MIN_REFERENCE_AGE)),
                float(data.get(CONF_MIN_DISTANCE_M, DEFAULT_MIN_DISTANCE_M)),
                float(data.get(CONF_DEFAULT_ACCURACY, DEFAULT_DEFAULT_ACCURACY)),
                int(data.get(CONF_STATIONARY_TIMEOUT, DEFAULT_STATIONARY_TIMEOUT)),
            )

        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN)

    async def async_start(self) -> None:
        """Restore recent samples once, then listen for live source updates."""
        await self._async_restore_history()
        for entity_id in self.histories:
            state = self.hass.states.get(entity_id)
            if state is not None:
                self._add_state(entity_id, state)
        self._publish(force=True)

        targets = list(self.histories)
        if not targets:
            return
        self.entry.async_on_unload(
            async_track_state_change_event(self.hass, targets, self._async_state_changed)
        )
        self.entry.async_on_unload(
            async_track_time_interval(
                self.hass,
                self._async_periodic_refresh,
                timedelta(seconds=ENTITY_REFRESH_INTERVAL),
            )
        )

    async def _async_restore_history(self) -> None:
        """Restore recent local Home Assistant history once at startup."""
        if not self.histories:
            return
        try:
            recorder = get_instance(self.hass)
            ready = await recorder.async_db_ready
        except (KeyError, RuntimeError):
            _LOGGER.debug("Recorder unavailable; starting with live samples")
            return
        if not ready:
            return

        end_time = dt_util.utcnow()
        start_time = end_time - timedelta(seconds=self._max_history_window)
        try:
            states_by_entity = await recorder.async_add_executor_job(
                history.get_significant_states,
                self.hass,
                start_time,
                end_time,
                list(self.histories),
                None,
                False,
                False,
                False,
                False,
                False,
            )
        except Exception:
            _LOGGER.exception("Unable to restore recent GeoMotion history")
            return

        for entity_id, states in states_by_entity.items():
            if entity_id not in self.histories:
                continue
            for state in states:
                if isinstance(state, State):
                    self._add_state(entity_id, state)

    @callback
    def _async_state_changed(self, event: Event[EventStateChangedData]) -> None:
        entity_id = event.data["entity_id"]
        new_state = event.data["new_state"]
        if new_state is None or entity_id not in self.histories:
            return
        self._add_state(entity_id, new_state)
        self._publish()

    @callback
    def _async_periodic_refresh(self, now: datetime) -> None:
        self._publish(now=now)

    @callback
    def _add_state(self, entity_id: str, state: State) -> None:
        sample = sample_from_state(state)
        if sample is not None:
            self.histories[entity_id].add_sample(sample)

    @callback
    def _evaluate_all(self, now: datetime | None = None) -> dict[str, MovementEvaluation]:
        now = now or dt_util.utcnow()
        return {key: value.evaluate(now=now) for key, value in self.histories.items()}

    @callback
    def _publish(self, *, force: bool = False, now: datetime | None = None) -> None:
        evaluations = self._evaluate_all(now)
        previous = self.data or {}
        changed = any(
            previous.get(entity_id) is None
            or previous[entity_id].is_moving != evaluation.is_moving
            or previous[entity_id].reason != evaluation.reason
            for entity_id, evaluation in evaluations.items()
        )
        monotonic_now = time.monotonic()
        if force or changed or monotonic_now - self._last_publish >= ENTITY_REFRESH_INTERVAL:
            self._last_publish = monotonic_now
            self.async_set_updated_data(evaluations)

    async def _async_update_data(self) -> dict[str, MovementEvaluation]:
        return self._evaluate_all()
