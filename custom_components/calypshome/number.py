"""Plateforme number pour Calyps'HOME : temps de montee et descente par volet."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .api import CalypshomeApi, CalypshomeApiError
from .const import DEFAULT_TRAVEL_TIME, DOMAIN

_LOGGER = logging.getLogger(__name__)

# registre partage : hass.data[DOMAIN]["travel"][object_id] = {"open": s, "close": s}
TRAVEL_KEY = "travel"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Cree deux curseurs (montee/descente) par volet."""
    api: CalypshomeApi = hass.data[DOMAIN][entry.entry_id]

    # registre des temps, partage avec la plateforme cover
    store = hass.data[DOMAIN].setdefault(TRAVEL_KEY, {})

    try:
        shutters = await api.get_shutters()
    except CalypshomeApiError as err:
        _LOGGER.error("Impossible de recuperer les volets : %s", err)
        return

    entities = []
    for s in shutters:
        oid = s["id"]
        store.setdefault(oid, {"open": DEFAULT_TRAVEL_TIME, "close": DEFAULT_TRAVEL_TIME})
        entities.append(CalypshomeTravelNumber(entry, store, oid, s["name"], "open"))
        entities.append(CalypshomeTravelNumber(entry, store, oid, s["name"], "close"))
        # curseur du pourcentage de la position favorite (defaut 50%)
        if "FAV_CALL_1" in s.get("actions", []):
            entities.append(CalypshomeFavoriteNumber(entry, store, oid, s["name"]))

    async_add_entities(entities)


class CalypshomeTravelNumber(NumberEntity, RestoreEntity):
    """Curseur de temps de course (montee ou descente) pour un volet."""

    _attr_has_entity_name = True
    _attr_native_min_value = 3
    _attr_native_max_value = 120
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        entry: ConfigEntry,
        store: dict,
        object_id: int,
        name: str,
        direction: str,  # "open" ou "close"
    ) -> None:
        self._store = store
        self._object_id = object_id
        self._direction = direction
        self._attr_translation_key = (
            "travel_time_up" if direction == "open" else "travel_time_down"
        )
        self._attr_unique_id = f"{DOMAIN}_{object_id}_travel_{direction}"
        self._attr_icon = "mdi:arrow-up-bold" if direction == "open" else "mdi:arrow-down-bold"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{object_id}")},
            name=name,
        )

    @property
    def native_value(self) -> float:
        return self._store.get(self._object_id, {}).get(self._direction, DEFAULT_TRAVEL_TIME)

    async def async_set_native_value(self, value: float) -> None:
        self._store.setdefault(self._object_id, {})[self._direction] = int(value)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restaure la derniere valeur connue au demarrage."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state not in (None, "unknown", "unavailable"):
            try:
                self._store.setdefault(self._object_id, {})[self._direction] = int(float(last.state))
            except (ValueError, TypeError):
                pass


class CalypshomeFavoriteNumber(NumberEntity, RestoreEntity):
    """Curseur du pourcentage correspondant a la position favorite du volet."""

    _attr_has_entity_name = True
    _attr_translation_key = "favorite_position_percent"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "%"
    _attr_mode = NumberMode.SLIDER
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:star-cog"

    def __init__(self, entry: ConfigEntry, store: dict, object_id: int, name: str) -> None:
        self._store = store
        self._object_id = object_id
        self._attr_unique_id = f"{DOMAIN}_{object_id}_fav_pct"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{object_id}")},
            name=name,
        )

    @property
    def native_value(self) -> float:
        return self._store.get(self._object_id, {}).get("fav_pct", 10)

    async def async_set_native_value(self, value: float) -> None:
        self._store.setdefault(self._object_id, {})["fav_pct"] = int(value)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state not in (None, "unknown", "unavailable"):
            try:
                self._store.setdefault(self._object_id, {})["fav_pct"] = int(float(last.state))
            except (ValueError, TypeError):
                pass
