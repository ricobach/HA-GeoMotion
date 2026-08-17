"""The GeoMotion integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import MovementCoordinator

PLATFORMS = [Platform.BINARY_SENSOR]


@dataclass(slots=True)
class GeoMotionRuntimeData:
    """Runtime data for GeoMotion."""

    movement_coordinator: MovementCoordinator


type GeoMotionConfigEntry = ConfigEntry[GeoMotionRuntimeData]


async def _async_reload_entry(hass: HomeAssistant, entry: GeoMotionConfigEntry) -> None:
    """Reload GeoMotion after entry changes."""
    await hass.config_entries.async_reload(entry.entry_id)


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
