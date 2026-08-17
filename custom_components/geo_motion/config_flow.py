"""Config flow for GeoMotion."""

from __future__ import annotations

from typing import Any, override

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

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
    SUBENTRY_TYPE_TRACKED_ENTITY,
)

SETTINGS_DEFAULTS = {
    CONF_HISTORY_WINDOW: DEFAULT_HISTORY_WINDOW,
    CONF_COMPARISON_AGE: DEFAULT_COMPARISON_AGE,
    CONF_MIN_REFERENCE_AGE: DEFAULT_MIN_REFERENCE_AGE,
    CONF_MIN_DISTANCE_M: DEFAULT_MIN_DISTANCE_M,
    CONF_DEFAULT_ACCURACY: DEFAULT_DEFAULT_ACCURACY,
    CONF_STATIONARY_TIMEOUT: DEFAULT_STATIONARY_TIMEOUT,
}


def _selector() -> EntitySelector:
    """Return the supported source entity selector."""
    return EntitySelector(EntitySelectorConfig(domain=["person", "device_tracker"]))


def _source_schema() -> vol.Schema:
    """Schema for adding a tracked source entity."""
    return vol.Schema({vol.Required(CONF_SOURCE_ENTITY): _selector()})


def _settings_schema() -> vol.Schema:
    """Schema for the settings shared by all GeoMotion sensors."""
    return vol.Schema(
        {
            vol.Optional(
                CONF_HISTORY_WINDOW, default=DEFAULT_HISTORY_WINDOW
            ): vol.All(int, vol.Range(min=120, max=3600)),
            vol.Optional(
                CONF_COMPARISON_AGE, default=DEFAULT_COMPARISON_AGE
            ): vol.All(int, vol.Range(min=60, max=1800)),
            vol.Optional(
                CONF_MIN_REFERENCE_AGE, default=DEFAULT_MIN_REFERENCE_AGE
            ): vol.All(int, vol.Range(min=30, max=600)),
            vol.Optional(
                CONF_MIN_DISTANCE_M, default=DEFAULT_MIN_DISTANCE_M
            ): vol.All(int, vol.Range(min=0, max=1000)),
            vol.Optional(
                CONF_DEFAULT_ACCURACY, default=DEFAULT_DEFAULT_ACCURACY
            ): vol.All(int, vol.Range(min=1, max=500)),
            vol.Optional(
                CONF_STATIONARY_TIMEOUT, default=DEFAULT_STATIONARY_TIMEOUT
            ): vol.All(int, vol.Range(min=0, max=900)),
        }
    )


def _friendly(flow: ConfigFlow | ConfigSubentryFlow, entity_id: str) -> str:
    """Return a friendly title for a source entity."""
    state = flow.hass.states.get(entity_id)
    return state.attributes.get("friendly_name", entity_id) if state else entity_id


class GeoMotionConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle GeoMotion configuration."""

    VERSION = 2

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return supported GeoMotion subentry types."""
        return {SUBENTRY_TYPE_TRACKED_ENTITY: GeoMotionTrackedEntityFlow}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the shared GeoMotion options flow."""
        return GeoMotionOptionsFlow()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create GeoMotion and its first tracked entity."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            source = user_input[CONF_SOURCE_ENTITY]
            return self.async_create_entry(
                title="GeoMotion",
                data={},
                options=dict(SETTINGS_DEFAULTS),
                subentries=[
                    {
                        "subentry_type": SUBENTRY_TYPE_TRACKED_ENTITY,
                        "data": {CONF_SOURCE_ENTITY: source},
                        "title": _friendly(self, source),
                        "unique_id": source,
                    }
                ],
            )

        return self.async_show_form(step_id="user", data_schema=_source_schema())


class GeoMotionOptionsFlow(OptionsFlow):
    """Manage settings shared by every GeoMotion sensor."""

    @override
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage shared movement settings."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = {
            key: self.config_entry.options.get(key, default)
            for key, default in SETTINGS_DEFAULTS.items()
        }
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                _settings_schema(), current
            ),
        )


class GeoMotionTrackedEntityFlow(ConfigSubentryFlow):
    """Add individual tracked entities to GeoMotion."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add one person or device tracker."""
        if user_input is not None:
            source = user_input[CONF_SOURCE_ENTITY]
            entry = self._get_entry()
            if any(item.unique_id == source for item in entry.subentries.values()):
                return self.async_abort(reason="already_configured")

            self.hass.config_entries.async_schedule_reload(entry.entry_id)
            return self.async_create_entry(
                title=_friendly(self, source),
                data={CONF_SOURCE_ENTITY: source},
                unique_id=source,
            )

        return self.async_show_form(step_id="user", data_schema=_source_schema())
