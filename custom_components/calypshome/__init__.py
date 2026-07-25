"""Integration Calyps'HOME (Avidsen cloud)."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CalypshomeApi, CalypshomeApiError, CalypshomeAuthError
from .const import CONF_LOGIN, CONF_PASSWORD, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.COVER, Platform.BUTTON, Platform.NUMBER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configure l'integration a partir d'une entree de configuration."""
    session = async_get_clientsession(hass)
    api = CalypshomeApi(session, entry.data[CONF_LOGIN], entry.data[CONF_PASSWORD])

    try:
        await api.authenticate()
    except CalypshomeAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except CalypshomeApiError as err:
        raise ConfigEntryNotReady(str(err)) from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = api

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Decharge l'integration."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Recharge l'integration quand les options changent (temps de course)."""
    await hass.config_entries.async_reload(entry.entry_id)
