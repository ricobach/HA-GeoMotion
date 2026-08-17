"""The GeoMotion integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

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
    SUBENTRY_TYPE_TRACKED_ENTITY,
)
from .coordinator import MovementCoordinator

PLATFORMS = [Platform.BINARY_SENSOR]

SETTINGS_DEFAULTS = {
    CONF_HISTORY_WINDOW: DEFAULT_HISTORY_WINDOW,
    CONF_COMPARISON_AGE: DEFAULT_COMPARISON_AGE,
    CONF_MIN_REFERENCE_AGE: DEFAULT_MIN_REFERENCE_AGE,
    CONF_MIN_DISTANCE_M: DEFAULT_MIN_DISTANCE_M,
    CONF_DEFAULT_ACCURACY: DEFAULT_DEFAULT_ACCURACY,
    CONF_STATIONARY_TIMEOUT: DEFAULT_STATIONARY_TIMEOUT,
}


@dataclass(slots=True)
class GeoMotionRuntimeData:
    """Runtime data for GeoMotion."""

    movement_coordinator: MovementCoordinator


type GeoMotionConfigEntry = ConfigEntry[GeoMotionRuntimeData]


async def _async_reload_entry(hass: HomeAssistant, entry: GeoMotionConfigEntry) -> None:
    """Reload GeoMotion after shared settings change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate per-person movement settings to one shared settings set."""
    if entry.version >= 2:
        return True

    if entry.version == 1:
        tracked_subentries = [
            subentry
            for subentry in entry.subentries.values()
            if subentry.subentry_type == SUBENTRY_TYPE_TRACKED_ENTITY
        ]

        shared_settings = dict(entry.options)
        source_settings = tracked_subentries[0].data if tracked_subentries else {}
        for key, default in SETTINGS_DEFAULTS.items():
            shared_settings[key] = shared_settings.get(
                key, source_settings.get(key, default)
            )

        for subentry in tracked_subentries:
            source = subentry.data.get(CONF_SOURCE_ENTITY)
            if source is None:
                continue
            new_data = {CONF_SOURCE_ENTITY: source}
            if dict(subentry.data) != new_data:
                hass.config_entries.async_update_subentry(
                    entry,
                    subentry,
                    data=new_data,
                )

        hass.config_entries.async_update_entry(
            entry,
            version=2,
            options=shared_settings,
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: GeoMotionConfigEntry) -> bool:
    """Set up GeoMotion from a config entry."""
    movement_coordinator = MovementCoordinator(hass, entry)
    await movement_coordinator.async_start()

    entry.runtime_data = GeoMotionRuntimeData(movement_coordinator=movement_coordinator)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GeoMotionConfigEntry) -> bool:
    """Unload GeoMotion."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
