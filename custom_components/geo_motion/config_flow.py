"""Config flow for GeoMotion."""

from __future__ import annotations

from typing import Any, override

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, ConfigSubentryFlow, SubentryFlowResult
from homeassistant.core import callback
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .const import CONF_COMPARISON_AGE, CONF_DEFAULT_ACCURACY, CONF_HISTORY_WINDOW, CONF_MIN_DISTANCE_M, CONF_MIN_REFERENCE_AGE, CONF_SOURCE_ENTITY, CONF_STATIONARY_TIMEOUT, DEFAULT_COMPARISON_AGE, DEFAULT_DEFAULT_ACCURACY, DEFAULT_HISTORY_WINDOW, DEFAULT_MIN_DISTANCE_M, DEFAULT_MIN_REFERENCE_AGE, DEFAULT_STATIONARY_TIMEOUT, DOMAIN, SUBENTRY_TYPE_TRACKED_ENTITY


def _selector() -> EntitySelector:
    return EntitySelector(EntitySelectorConfig(domain=["person", "device_tracker"]))


def _schema(include_source: bool = True) -> vol.Schema:
    data: dict[Any, Any] = {}
    if include_source:
        data[vol.Required(CONF_SOURCE_ENTITY)] = _selector()
    data.update({
        vol.Optional(CONF_HISTORY_WINDOW, default=DEFAULT_HISTORY_WINDOW): vol.All(int, vol.Range(min=120, max=3600)),
        vol.Optional(CONF_COMPARISON_AGE, default=DEFAULT_COMPARISON_AGE): vol.All(int, vol.Range(min=60, max=1800)),
        vol.Optional(CONF_MIN_REFERENCE_AGE, default=DEFAULT_MIN_REFERENCE_AGE): vol.All(int, vol.Range(min=30, max=600)),
        vol.Optional(CONF_MIN_DISTANCE_M, default=DEFAULT_MIN_DISTANCE_M): vol.All(int, vol.Range(min=0, max=1000)),
        vol.Optional(CONF_DEFAULT_ACCURACY, default=DEFAULT_DEFAULT_ACCURACY): vol.All(int, vol.Range(min=1, max=500)),
        vol.Optional(CONF_STATIONARY_TIMEOUT, default=DEFAULT_STATIONARY_TIMEOUT): vol.All(int, vol.Range(min=0, max=900)),
    })
    return vol.Schema(data)


def _friendly(flow: ConfigFlow | ConfigSubentryFlow, entity_id: str) -> str:
    state = flow.hass.states.get(entity_id)
    return state.attributes.get("friendly_name", entity_id) if state else entity_id


class GeoMotionConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(cls, config_entry: ConfigEntry) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_TYPE_TRACKED_ENTITY: GeoMotionTrackedEntityFlow}

    @override
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            source = user_input[CONF_SOURCE_ENTITY]
            return self.async_create_entry(
                title="GeoMotion",
                data={},
                subentries=[{
                    "subentry_type": SUBENTRY_TYPE_TRACKED_ENTITY,
                    "data": dict(user_input),
                    "title": _friendly(self, source),
                    "unique_id": source,
                }],
            )
        return self.async_show_form(step_id="user", data_schema=_schema())


class GeoMotionTrackedEntityFlow(ConfigSubentryFlow):
    @override
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        if user_input is not None:
            source = user_input[CONF_SOURCE_ENTITY]
            entry = self._get_entry()
            if any(item.unique_id == source for item in entry.subentries.values()):
                return self.async_abort(reason="already_configured")
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
            return self.async_create_entry(title=_friendly(self, source), data=dict(user_input), unique_id=source)
        return self.async_show_form(step_id="user", data_schema=_schema())

    @override
    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        if user_input is not None:
            updated = dict(subentry.data)
            updated.update(user_input)
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
            return self.async_update_and_abort(entry, subentry, data=updated, title=subentry.title)
        current = {key: value for key, value in subentry.data.items() if key != CONF_SOURCE_ENTITY}
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(_schema(include_source=False), current),
            description_placeholders={"source": subentry.title},
        )
