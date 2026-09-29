"""Config and options flow for AR Motion AI."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .const import (
    CONF_AI_TASK,
    CONF_CAMERA,
    CONF_COOLDOWN,
    CONF_INTERVAL,
    CONF_MOTION_SENSORS,
    CONF_NAME,
    CONF_NOTIFY,
    CONF_NOTIFY_NO_MOTION,
    CONF_NUM_SNAPSHOTS,
    CONF_PROMPT,
    DEFAULT_COOLDOWN,
    DEFAULT_INTERVAL,
    DEFAULT_NOTIFY_NO_MOTION,
    DEFAULT_NUM_SNAPSHOTS,
    DEFAULT_PROMPT,
    DOMAIN,
)


def _notify_options(hass: HomeAssistant) -> list[selector.SelectOptionDict]:
    services = sorted(hass.services.async_services_for_domain("notify"))
    # Put phones first
    services.sort(key=lambda s: (not s.startswith("mobile_app_"), s))
    return [
        selector.SelectOptionDict(value=s, label=f"notify.{s}")
        for s in services
        if s not in ("send_message", "persistent_notification")
    ]


def _schema(hass: HomeAssistant, d: dict[str, Any], include_name: bool) -> vol.Schema:
    fields: dict[Any, Any] = {}
    if include_name:
        fields[vol.Required(CONF_NAME, default=d.get(CONF_NAME, ""))] = selector.TextSelector()
    fields.update(
        {
            vol.Required(CONF_CAMERA, default=d.get(CONF_CAMERA, vol.UNDEFINED)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="camera")
            ),
            vol.Required(
                CONF_MOTION_SENSORS, default=d.get(CONF_MOTION_SENSORS, vol.UNDEFINED)
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="binary_sensor", multiple=True)
            ),
            vol.Required(CONF_AI_TASK, default=d.get(CONF_AI_TASK, vol.UNDEFINED)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="ai_task")
            ),
            vol.Optional(CONF_NOTIFY, default=d.get(CONF_NOTIFY, [])): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=_notify_options(hass),
                    multiple=True,
                    custom_value=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_NUM_SNAPSHOTS, default=d.get(CONF_NUM_SNAPSHOTS, DEFAULT_NUM_SNAPSHOTS)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=5, step=1, mode=selector.NumberSelectorMode.SLIDER)
            ),
            vol.Required(CONF_INTERVAL, default=d.get(CONF_INTERVAL, DEFAULT_INTERVAL)): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=5000, step=100, unit_of_measurement="ms", mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Required(CONF_COOLDOWN, default=d.get(CONF_COOLDOWN, DEFAULT_COOLDOWN)): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=3600, step=5, unit_of_measurement="s", mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Required(
                CONF_NOTIFY_NO_MOTION, default=d.get(CONF_NOTIFY_NO_MOTION, DEFAULT_NOTIFY_NO_MOTION)
            ): selector.BooleanSelector(),
            vol.Required(CONF_PROMPT, default=d.get(CONF_PROMPT, DEFAULT_PROMPT)): selector.TextSelector(
                selector.TextSelectorConfig(multiline=True)
            ),
        }
    )
    return vol.Schema(fields)


def _clean(user_input: dict[str, Any]) -> dict[str, Any]:
    out = dict(user_input)
    for k in (CONF_NUM_SNAPSHOTS, CONF_INTERVAL, CONF_COOLDOWN):
        if k in out:
            out[k] = int(out[k])
    return out


class MotionAIConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data = _clean(user_input)
            if not data.get(CONF_MOTION_SENSORS):
                errors[CONF_MOTION_SENSORS] = "no_sensors"
            else:
                await self.async_set_unique_id(f"{data[CONF_CAMERA]}")
                self._abort_if_unique_id_configured()
                title = data.get(CONF_NAME) or data[CONF_CAMERA]
                data[CONF_NAME] = title
                return self.async_create_entry(title=title, data=data)
        return self.async_show_form(
            step_id="user",
            data_schema=_schema(self.hass, user_input or {}, include_name=True),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return MotionAIOptionsFlow()


class MotionAIOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=_clean(user_input))
        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init", data_schema=_schema(self.hass, current, include_name=False)
        )
