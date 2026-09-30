"""Config and options flow for AR Motion AI.

Step 1 (user/init): camera, sensors, notify targets, tuning, AI provider
Step 2 (ai):        API key / server URL (or AI Task entity) — validated live
Step 3 (model):     pick a model from the list your account actually has
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .const import (
    CONF_AI_TASK,
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_CAMERA,
    CONF_COOLDOWN,
    CONF_INTERVAL,
    CONF_MODEL,
    CONF_MOTION_SENSORS,
    CONF_NAME,
    CONF_NOTIFY,
    CONF_NOTIFY_NO_MOTION,
    CONF_NUM_SNAPSHOTS,
    CONF_PROMPT,
    CONF_PROVIDER,
    DEFAULT_COOLDOWN,
    DEFAULT_INTERVAL,
    DEFAULT_MODELS,
    DEFAULT_NOTIFY_NO_MOTION,
    DEFAULT_NUM_SNAPSHOTS,
    DEFAULT_OLLAMA_URL,
    DEFAULT_PROMPT,
    DEFAULT_PROVIDER,
    DOMAIN,
    PROVIDER_AI_TASK,
    PROVIDER_ANTHROPIC,
    PROVIDER_GEMINI,
    PROVIDER_OLLAMA,
    PROVIDER_OPENAI,
    PROVIDERS,
)
from .providers import ProviderError, async_list_models

KEY_PROVIDERS = (PROVIDER_GEMINI, PROVIDER_OPENAI, PROVIDER_ANTHROPIC)
PREFERRED_HINTS = ("flash", "mini", "haiku", "vl", "llava")


def _notify_options(hass: HomeAssistant) -> list[selector.SelectOptionDict]:
    services = sorted(hass.services.async_services_for_domain("notify"))
    services.sort(key=lambda s: (not s.startswith("mobile_app_"), s))
    return [
        selector.SelectOptionDict(value=s, label=f"notify.{s}")
        for s in services
        if s not in ("send_message", "persistent_notification")
    ]


def _main_schema(hass: HomeAssistant, d: dict[str, Any], include_name: bool) -> vol.Schema:
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
            vol.Required(
                CONF_PROVIDER, default=d.get(CONF_PROVIDER) or (PROVIDER_AI_TASK if d.get(CONF_AI_TASK) else DEFAULT_PROVIDER)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=PROVIDERS,
                    translation_key=CONF_PROVIDER,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
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


def _ai_schema(provider: str, d: dict[str, Any]) -> vol.Schema:
    password = selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD))
    url = selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.URL))
    if provider == PROVIDER_AI_TASK:
        return vol.Schema(
            {
                vol.Required(CONF_AI_TASK, default=d.get(CONF_AI_TASK, vol.UNDEFINED)): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="ai_task")
                )
            }
        )
    if provider in KEY_PROVIDERS:
        return vol.Schema({vol.Required(CONF_API_KEY, default=d.get(CONF_API_KEY, vol.UNDEFINED)): password})
    if provider == PROVIDER_OLLAMA:
        return vol.Schema({vol.Required(CONF_BASE_URL, default=d.get(CONF_BASE_URL) or DEFAULT_OLLAMA_URL): url})
    # OpenAI-compatible (OpenRouter, LocalAI, LM Studio, Groq, ...)
    return vol.Schema(
        {
            vol.Required(CONF_BASE_URL, default=d.get(CONF_BASE_URL, vol.UNDEFINED)): url,
            vol.Optional(CONF_API_KEY, default=d.get(CONF_API_KEY, "")): password,
        }
    )


def _pick_default_model(provider: str, models: list[str], previous: str | None) -> str:
    if previous and (previous in models or not models):
        return previous
    preferred = DEFAULT_MODELS.get(provider)
    if preferred and (preferred in models or not models):
        return preferred
    for hint in PREFERRED_HINTS:
        for m in models:
            if hint in m:
                return m
    return models[0] if models else ""


def _clean(user_input: dict[str, Any]) -> dict[str, Any]:
    out = dict(user_input)
    for k in (CONF_NUM_SNAPSHOTS, CONF_INTERVAL, CONF_COOLDOWN):
        if k in out:
            out[k] = int(out[k])
    return out


class _FlowMixin:
    """Shared provider/model steps for config + options flows."""

    hass: HomeAssistant
    _data: dict[str, Any]
    _previous: dict[str, Any]
    _models: list[str]

    async def async_step_ai(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        provider = self._data[CONF_PROVIDER]
        prev = self._previous if self._previous.get(CONF_PROVIDER) == provider else {}
        errors: dict[str, str] = {}
        placeholders = {"error_detail": ""}

        if user_input is not None:
            self._data.update(user_input)
            if provider == PROVIDER_AI_TASK:
                return await self._async_finish()
            try:
                self._models = await async_list_models(
                    self.hass, provider, user_input.get(CONF_API_KEY), user_input.get(CONF_BASE_URL)
                )
            except ProviderError as err:
                errors["base"] = err.code if err.code in ("invalid_auth", "cannot_connect", "no_credit", "rate_limited") else "unknown"
                placeholders["error_detail"] = str(err)
            else:
                return await self.async_step_model()

        return self.async_show_form(  # type: ignore[attr-defined]
            step_id="ai",
            data_schema=_ai_schema(provider, user_input or prev),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_model(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        provider = self._data[CONF_PROVIDER]
        if user_input is not None:
            self._data[CONF_MODEL] = user_input[CONF_MODEL].strip()
            return await self._async_finish()

        prev_model = self._previous.get(CONF_MODEL) if self._previous.get(CONF_PROVIDER) == provider else None
        default = _pick_default_model(provider, self._models, prev_model)
        options = list(self._models)
        if default and default not in options:
            options.insert(0, default)
        return self.async_show_form(  # type: ignore[attr-defined]
            step_id="model",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MODEL, default=default or vol.UNDEFINED): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options, custom_value=True, mode=selector.SelectSelectorMode.DROPDOWN
                        )
                    )
                }
            ),
            description_placeholders={"count": str(len(self._models))},
        )

    async def _async_finish(self) -> ConfigFlowResult:
        raise NotImplementedError


class MotionAIConfigFlow(_FlowMixin, ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._data = {}
        self._previous = {}
        self._models = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data = _clean(user_input)
            if not data.get(CONF_MOTION_SENSORS):
                errors[CONF_MOTION_SENSORS] = "no_sensors"
            else:
                await self.async_set_unique_id(f"{data[CONF_CAMERA]}")
                self._abort_if_unique_id_configured()
                data[CONF_NAME] = data.get(CONF_NAME) or data[CONF_CAMERA]
                self._data = data
                return await self.async_step_ai()
        return self.async_show_form(
            step_id="user",
            data_schema=_main_schema(self.hass, user_input or {}, include_name=True),
            errors=errors,
        )

    async def _async_finish(self) -> ConfigFlowResult:
        return self.async_create_entry(title=self._data[CONF_NAME], data=self._data)

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return MotionAIOptionsFlow()


class MotionAIOptionsFlow(_FlowMixin, OptionsFlow):
    def __init__(self) -> None:
        self._data = {}
        self._previous = {}
        self._models = []

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        current = {**self.config_entry.data, **self.config_entry.options}
        if not current.get(CONF_PROVIDER) and current.get(CONF_AI_TASK):
            current[CONF_PROVIDER] = PROVIDER_AI_TASK
        self._previous = current
        if user_input is not None:
            self._data = _clean(user_input)
            return await self.async_step_ai()
        return self.async_show_form(
            step_id="init", data_schema=_main_schema(self.hass, current, include_name=False)
        )

    async def _async_finish(self) -> ConfigFlowResult:
        return self.async_create_entry(data=self._data)
