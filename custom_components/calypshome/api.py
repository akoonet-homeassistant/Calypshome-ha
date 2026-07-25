"""Client pour l'API cloud Calyps'HOME / Avidsen."""
from __future__ import annotations

import logging
import time
import uuid

import aiohttp

from .const import BASE_URL, LOGIN_PATH, OBJECTS_PATH, SHUTTER_TYPE

_LOGGER = logging.getLogger(__name__)

# Le JWT contient un champ "exp" mais pour rester simple on suppose ~6h.
TOKEN_LIFETIME = 6 * 3600


class CalypshomeApiError(Exception):
    """Erreur generique de l'API."""


class CalypshomeAuthError(CalypshomeApiError):
    """Erreur d'authentification (identifiants invalides)."""


class CalypshomeApi:
    """Client asynchrone de l'API Calyps'HOME cloud."""

    def __init__(self, session: aiohttp.ClientSession, login: str, password: str) -> None:
        self._session = session
        self._login = login
        self._password = password
        self._token: str | None = None
        self._token_ts: float = 0.0
        # deviceID STABLE derive du login : deterministe, donc identique a chaque
        # demarrage. Cela evite d'enregistrer un nouvel appareil a chaque fois
        # (erreur "too_much_mobiles"), tout en gardant un appareil dedie a Home
        # Assistant et sans exposer d'identifiant personnel.
        self._device_id = str(
            uuid.uuid5(uuid.NAMESPACE_DNS, f"ha-calypshome-{login}")
        ).upper()
        self._headers = {
            "Content-Type": "application/json;charset=utf-8",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "CalypsHome/61 CFNetwork/3860.600.12 Darwin/25.5.0",
        }

    async def authenticate(self) -> None:
        """Recupere un token JWT."""
        url = f"{BASE_URL}{LOGIN_PATH}"
        payload = {
            "login": self._login,
            "password": self._password,
            "stayConnected": "on",
            "deviceID": self._device_id,
            "deviceOS": "IOS",
            "deviceType": "iPhone18,3",
        }
        try:
            async with self._session.post(
                url, json=payload, headers=self._headers, timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                if resp.status == 401 or resp.status == 403:
                    raise CalypshomeAuthError(f"Login refuse (HTTP {resp.status})")
                if resp.status != 200:
                    text = await resp.text()
                    raise CalypshomeApiError(f"Login HTTP {resp.status} : {text[:200]}")
                data = await resp.json()
        except aiohttp.ClientError as err:
            raise CalypshomeApiError(f"Erreur reseau login : {err}") from err

        token = data.get("token")
        if not token:
            raise CalypshomeAuthError("Pas de token dans la reponse de login")
        self._token = token
        self._token_ts = time.time()
        _LOGGER.debug("Authentification reussie (userId=%s)", data.get("userId"))

    async def _ensure_token(self) -> None:
        if self._token is None or (time.time() - self._token_ts) > (TOKEN_LIFETIME - 600):
            await self.authenticate()

    def _auth_headers(self) -> dict:
        h = dict(self._headers)
        h["Authorization"] = f"Bearer {self._token}"
        return h

    async def get_shutters(self) -> list[dict]:
        """Retourne la liste des volets {id, name, actions} en suivant la pagination."""
        await self._ensure_token()
        items: list[dict] = []
        url: str | None = f"{BASE_URL}{OBJECTS_PATH}"

        while url:
            try:
                async with self._session.get(
                    url, headers=self._auth_headers(), timeout=aiohttp.ClientTimeout(total=20)
                ) as resp:
                    if resp.status == 401:
                        # token expire : on re-login une fois
                        await self.authenticate()
                        async with self._session.get(
                            url, headers=self._auth_headers(),
                            timeout=aiohttp.ClientTimeout(total=20),
                        ) as resp2:
                            data = await resp2.json()
                    elif resp.status != 200:
                        text = await resp.text()
                        raise CalypshomeApiError(f"getObjects HTTP {resp.status} : {text[:200]}")
                    else:
                        data = await resp.json()
            except aiohttp.ClientError as err:
                raise CalypshomeApiError(f"Erreur reseau getObjects : {err}") from err

            for entry in data.get("content", []):
                res = entry.get("resource", {})
                if res.get("typeName") == SHUTTER_TYPE and not res.get("flags", {}).get("hidden"):
                    items.append({
                        "id": res.get("id"),
                        "name": res.get("name") or f"Volet {res.get('id')}",
                        "actions": [a.get("name") for a in res.get("actions", [])],
                    })
            url = data.get("next")

        _LOGGER.debug("%d volets recuperes", len(items))
        return items

    async def send_action(self, object_id: int, action: str) -> bool:
        """Envoie une action (OPEN/CLOSE/STOP) a un volet."""
        await self._ensure_token()
        url = f"{BASE_URL}{OBJECTS_PATH}/{object_id}"
        payload = {"actions": [{"name": action}]}
        try:
            async with self._session.put(
                url, json=payload, headers=self._auth_headers(),
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status == 401:
                    await self.authenticate()
                    async with self._session.put(
                        url, json=payload, headers=self._auth_headers(),
                        timeout=aiohttp.ClientTimeout(total=20),
                    ) as resp2:
                        return resp2.status == 200
                if resp.status != 200:
                    text = await resp.text()
                    _LOGGER.warning("Action %s sur %s : HTTP %s %s",
                                    action, object_id, resp.status, text[:150])
                return resp.status == 200
        except aiohttp.ClientError as err:
            _LOGGER.error("Erreur reseau action %s : %s", action, err)
            return False
