"""Binary sensor platform for GeoMotion."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GeoMotionConfigEntry
from .const import CONF_SOURCE_ENTITY, DOMAIN, SUBENTRY_TYPE_TRACKED_ENTITY
from .coordinator import MovementCoordinator
from .movement import MovementEvaluation


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GeoMotionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one moving binary sensor per tracked subentry."""
    coordinator = entry.runtime_data.movement_coordinator
    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_TYPE_TRACKED_ENTITY:
            continue
        source = subentry.data[CONF_SOURCE_ENTITY]
        async_add_entities(
            [GeoMotionBinarySensor(coordinator, entry, subentry_id, source, subentry.title)],
            config_subentry_id=subentry_id,
        )


class GeoMotionBinarySensor(CoordinatorEntity[MovementCoordinator], BinarySensorEntity):
    """GPS-derived movement state."""

    _attr_device_class = BinarySensorDeviceClass.MOVING
    _attr_has_entity_name = True
    _attr_translation_key = "moving"

    def __init__(
        self,
        coordinator: MovementCoordinator,
        entry: GeoMotionConfigEntry,
        subentry_id: str,
        source_entity: str,
        device_name: str,
    ) -> None:
        super().__init__(coordinator, context=source_entity)
        self._source = source_entity
        self._attr_unique_id = f"{entry.entry_id}_{source_entity}_moving"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)},
            name=device_name,
        )

    @property
    def _evaluation(self) -> MovementEvaluation | None:
        return (self.coordinator.data or {}).get(self._source)

    @property
    def is_on(self) -> bool | None:
        evaluation = self._evaluation
        return evaluation.is_moving if evaluation else None

    @property
    def entity_picture(self) -> str | None:
        if not self.hass:
            return None
        state = self.hass.states.get(self._source)
        return state.attributes.get("entity_picture") if state else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        evaluation = self._evaluation
        attrs: dict[str, Any] = {"source_entity": self._source}
        if evaluation is None:
            return attrs

        attrs.update(
            {
                "evaluation_reason": evaluation.reason,
                "gps_samples": evaluation.sample_count,
                "reference_age_seconds": evaluation.reference_age,
                "displacement_m": evaluation.displacement_m,
                "effective_movement_threshold_m": evaluation.effective_threshold_m,
                "last_meaningful_movement": (
                    evaluation.last_meaningful_movement.isoformat()
                    if evaluation.last_meaningful_movement
                    else None
                ),
            }
        )
        if evaluation.current is not None:
            attrs.update(
                {
                    "current_latitude": evaluation.current.latitude,
                    "current_longitude": evaluation.current.longitude,
                    "current_gps_accuracy": evaluation.current.accuracy,
                }
            )
        if evaluation.reference is not None:
            attrs.update(
                {
                    "reference_latitude": evaluation.reference.latitude,
                    "reference_longitude": evaluation.reference.longitude,
                    "reference_gps_accuracy": evaluation.reference.accuracy,
                }
            )
        return {key: value for key, value in attrs.items() if value is not None}
