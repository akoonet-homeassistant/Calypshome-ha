"""Config flow pour Calyps'HOME."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CalypshomeApi, CalypshomeApiError, CalypshomeAuthError
from .const import (
    CONF_LOGIN,
    CONF_PASSWORD,
    CONF_TRAVEL_TIMES,
    DEFAULT_TRAVEL_TIME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LOGIN): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class CalypshomeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Gere le flux de configuration initial."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            api = CalypshomeApi(session, user_input[CONF_LOGIN], user_input[CONF_PASSWORD])
            try:
                await api.authenticate()
            except CalypshomeAuthError:
                errors["base"] = "invalid_auth"
            except CalypshomeApiError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(user_input[CONF_LOGIN].lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_LOGIN], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return CalypshomeOptionsFlow()


class CalypshomeOptionsFlow(OptionsFlow):
    """Permet de regler le temps de course par volet."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Affiche un champ temps d'ouverture ET de fermeture par volet."""
        api: CalypshomeApi = self.hass.data[DOMAIN][self.config_entry.entry_id]

        if user_input is not None:
            # user_input contient open_<id> et close_<id> -> on reconstruit le dict
            travel: dict[str, dict[str, int]] = {}
            for key, val in user_input.items():
                if key.startswith("open_"):
                    sid = key.replace("open_", "")
                    travel.setdefault(sid, {})["open"] = val
                elif key.startswith("close_"):
                    sid = key.replace("close_", "")
                    travel.setdefault(sid, {})["close"] = val
            return self.async_create_entry(
                title="", data={CONF_TRAVEL_TIMES: travel}
            )

        try:
            shutters = await api.get_shutters()
        except CalypshomeApiError:
            shutters = []

        current = self.config_entry.options.get(CONF_TRAVEL_TIMES, {})
        schema_dict = {}
        for s in shutters:
            sid = str(s["id"])
            cur = current.get(sid, {})
            open_def = cur.get("open", DEFAULT_TRAVEL_TIME)
            close_def = cur.get("close", DEFAULT_TRAVEL_TIME)
            name = s["name"]
            # Deux champs distincts, prefixes par le nom du volet pour s'y retrouver
            schema_dict[
                vol.Optional(
                    f"open_{sid}",
                    default=open_def,
                    description={"suggested_value": open_def},
                )
            ] = vol.All(vol.Coerce(int), vol.Range(min=3, max=120))
            schema_dict[
                vol.Optional(
                    f"close_{sid}",
                    default=close_def,
                    description={"suggested_value": close_def},
                )
            ] = vol.All(vol.Coerce(int), vol.Range(min=3, max=120))

        # liste lisible ID -> nom pour aider l'utilisateur a remplir les champs
        legende = "\n".join(f"- {s['name']} = id {s['id']}" for s in shutters)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={
                "count": str(len(shutters)),
                "legende": legende,
            },
        )
