"""Plateforme button pour Calyps'HOME : rappel de la position favorite."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import CalypshomeApi, CalypshomeApiError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

FAVORITE_ACTION = "FAV_CALL_1"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Cree un bouton 'Position favorite' par volet."""
    api: CalypshomeApi = hass.data[DOMAIN][entry.entry_id]
    store = hass.data[DOMAIN].setdefault("travel", {})

    try:
        shutters = await api.get_shutters()
    except CalypshomeApiError as err:
        _LOGGER.error("Impossible de recuperer les volets : %s", err)
        return

    entities = []
    for s in shutters:
        # on n'ajoute le bouton que si le volet supporte FAV_CALL_1
        if FAVORITE_ACTION in s.get("actions", []):
            entities.append(CalypshomeFavoriteButton(api, entry, store, s["id"], s["name"]))

    async_add_entities(entities)


class CalypshomeFavoriteButton(ButtonEntity):
    """Bouton qui rappelle la position favorite memorisee dans le moteur."""

    _attr_icon = "mdi:star"
    _attr_has_entity_name = True
    _attr_translation_key = "favorite_position"

    def __init__(
        self,
        api: CalypshomeApi,
        entry: ConfigEntry,
        store: dict,
        object_id: int,
        name: str,
    ) -> None:
        self._api = api
        self._hass_store = store
        self._object_id = object_id
        self._attr_unique_id = f"{DOMAIN}_{object_id}_fav"
        # rattache au meme appareil que le volet correspondant
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{object_id}")},
            name=name,
        )

    async def async_press(self) -> None:
        """Rappelle la position favorite et recale la position estimee du cover."""
        store = self._hass_store
        cover = store.get("_covers", {}).get(self._object_id)
        fav_pct = store.get(self._object_id, {}).get("fav_pct", 10)
        if cover is not None:
            # le cover gere l'envoi FAV_CALL_1 + le recalage de position
            await cover.async_go_favorite(fav_pct)
        else:
            # repli : envoi direct si le cover n'est pas encore enregistre
            ok = await self._api.send_action(self._object_id, FAVORITE_ACTION)
            if not ok:
                _LOGGER.warning(
                    "Echec du rappel de position favorite pour le volet %s",
                    self._object_id,
                )
