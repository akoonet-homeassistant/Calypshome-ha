"""Plateforme cover pour Calyps'HOME."""
from __future__ import annotations

import logging
import time

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity

from datetime import timedelta

from .api import CalypshomeApi, CalypshomeApiError
from .const import CONF_TRAVEL_TIMES, DEFAULT_TRAVEL_TIME, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Frequence de rafraichissement de la position estimee pendant un mouvement.
POSITION_TICK = timedelta(seconds=1)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Met en place les entites volet."""
    api: CalypshomeApi = hass.data[DOMAIN][entry.entry_id]
    # registre partage avec la plateforme number
    store = hass.data[DOMAIN].setdefault("travel", {})
    # anciennes valeurs d'options (repli / compat)
    travel_times = entry.options.get(CONF_TRAVEL_TIMES, {})

    try:
        shutters = await api.get_shutters()
    except CalypshomeApiError as err:
        _LOGGER.error("Impossible de recuperer les volets : %s", err)
        return

    entities = []
    for s in shutters:
        oid = s["id"]
        # priorite aux options si presentes, sinon valeurs par defaut (les number prendront le relais)
        cfg = travel_times.get(str(oid), {})
        open_time = int(cfg.get("open", DEFAULT_TRAVEL_TIME))
        close_time = int(cfg.get("close", DEFAULT_TRAVEL_TIME))
        entities.append(
            CalypshomeCover(api, entry, store, oid, s["name"], open_time, close_time)
        )

    async_add_entities(entities)


class CalypshomeCover(CoverEntity, RestoreEntity):
    """Un volet roulant Profalux pilote via le cloud Avidsen."""

    _attr_device_class = CoverDeviceClass.SHUTTER
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(
        self,
        api: CalypshomeApi,
        entry: ConfigEntry,
        store: dict,
        object_id: int,
        name: str,
        open_time: int,
        close_time: int,
    ) -> None:
        self._api = api
        self._store = store
        self._object_id = object_id
        self._attr_unique_id = f"{DOMAIN}_{object_id}"
        # valeurs initiales : seedent le registre si pas deja present
        store.setdefault(object_id, {"open": max(open_time, 1), "close": max(close_time, 1)})

        # Position estimee : 100 = ouvert, 0 = ferme. Inconnue au depart -> on suppose ouvert.
        self._position = 100
        self._moving = False
        self._move_dir = 0  # +1 ouverture, -1 fermeture
        self._move_start_ts = 0.0
        self._move_start_pos = 100
        self._target_pos: int | None = None
        self._unsub_tick = None

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{object_id}")},
            name=name,
            manufacturer="Profalux / Avidsen",
            model="Volet Neosol 868",
        )

    async def async_added_to_hass(self) -> None:
        """Enregistre l'entite et restaure la derniere position estimee."""
        await super().async_added_to_hass()
        covers = self._store.setdefault("_covers", {})
        covers[self._object_id] = self

        # restauration de la derniere position connue avant redemarrage
        last = await self.async_get_last_state()
        if last is not None:
            pos = last.attributes.get("current_position")
            if pos is not None:
                try:
                    self._position = max(0, min(100, int(pos)))
                except (ValueError, TypeError):
                    pass

    async def async_go_favorite(self, favorite_position: int) -> None:
        """Rappelle la position favorite du moteur et recale la position estimee."""
        if await self._api.send_action(self._object_id, "FAV_CALL_1"):
            # le moteur va a sa position memorisee : on stoppe toute estimation
            # en cours et on force la position connue fournie par l'utilisateur.
            self._finish_move()
            self._position = max(0, min(100, int(favorite_position)))
            self.async_write_ha_state()

    # ----- proprietes -----

    @property
    def current_cover_position(self) -> int | None:
        return int(self._position)

    @property
    def is_closed(self) -> bool | None:
        return self._position <= 0

    @property
    def is_opening(self) -> bool:
        return self._moving and self._move_dir > 0

    @property
    def is_closing(self) -> bool:
        return self._moving and self._move_dir < 0

    # ----- commandes -----

    async def async_open_cover(self, **kwargs) -> None:
        if await self._api.send_action(self._object_id, "OPEN"):
            self._start_move(+1, target=100)

    async def async_close_cover(self, **kwargs) -> None:
        if await self._api.send_action(self._object_id, "CLOSE"):
            self._start_move(-1, target=0)

    async def async_stop_cover(self, **kwargs) -> None:
        if await self._api.send_action(self._object_id, "STOP"):
            self._finish_move()

    async def async_set_cover_position(self, **kwargs) -> None:
        target = kwargs[ATTR_POSITION]
        if target == self._position:
            return
        direction = +1 if target > self._position else -1
        action = "OPEN" if direction > 0 else "CLOSE"
        if await self._api.send_action(self._object_id, action):
            self._start_move(direction, target=target)

    # ----- estimation de position par minuterie -----

    def _start_move(self, direction: int, target: int) -> None:
        self._update_position()  # fige la position courante avant de repartir
        self._moving = True
        self._move_dir = direction
        self._move_start_ts = time.time()
        self._move_start_pos = self._position
        self._target_pos = target
        if self._unsub_tick is None:
            self._unsub_tick = async_track_time_interval(
                self.hass, self._async_tick, POSITION_TICK
            )
        self.async_write_ha_state()

    @callback
    def _async_tick(self, now) -> None:
        if not self._moving:
            return
        self._update_position()
        # arret automatique a l'arrivee
        if self._target_pos is not None:
            if (self._move_dir > 0 and self._position >= self._target_pos) or (
                self._move_dir < 0 and self._position <= self._target_pos
            ):
                # si la cible est une position intermediaire, on envoie STOP
                if 0 < self._target_pos < 100:
                    self.hass.async_create_task(
                        self._api.send_action(self._object_id, "STOP")
                    )
                self._finish_move()
        self.async_write_ha_state()

    def _update_position(self) -> None:
        if not self._moving:
            return
        elapsed = time.time() - self._move_start_ts
        # temps de course selon le sens : ouverture (+1) ou fermeture (-1)
        # temps de course lus dynamiquement depuis le registre (curseurs number)
        times = self._store.get(self._object_id, {})
        if self._move_dir > 0:
            travel = max(int(times.get("open", 20)), 1)
        else:
            travel = max(int(times.get("close", 20)), 1)
        delta = (elapsed / travel) * 100 * self._move_dir
        new_pos = self._move_start_pos + delta
        self._position = max(0, min(100, int(round(new_pos))))

    def _finish_move(self) -> None:
        self._update_position()
        self._moving = False
        self._move_dir = 0
        self._target_pos = None
        if self._unsub_tick is not None:
            self._unsub_tick()
            self._unsub_tick = None
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_tick is not None:
            self._unsub_tick()
            self._unsub_tick = None
