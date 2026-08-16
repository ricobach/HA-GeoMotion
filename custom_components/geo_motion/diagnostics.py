"""Diagnostics for GeoMotion."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import GeoMotionConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: GeoMotionConfigEntry
) -> dict[str, Any]:
    """Return diagnostics without exposing rolling GPS history."""
    coordinator = entry.runtime_data.movement_coordinator
    data = coordinator.data or {}
    return {
        "subentries": {
            subentry.subentry_id: {
                "title": subentry.title,
                "data": dict(subentry.data),
                "evaluation": (
                    {
                        "is_moving": evaluation.is_moving,
                        "reason": evaluation.reason,
                        "sample_count": evaluation.sample_count,
                        "reference_age": evaluation.reference_age,
                        "displacement_m": evaluation.displacement_m,
                        "effective_threshold_m": evaluation.effective_threshold_m,
                    }
                    if (evaluation := data.get(subentry.data["source_entity"]))
                    else None
                ),
            }
            for subentry in entry.subentries.values()
        }
    }
