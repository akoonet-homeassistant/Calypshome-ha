"""Constantes pour l'integration Calyps'HOME (Avidsen cloud)."""

DOMAIN = "calypshome"

BASE_URL = "https://calypshome.avidsen.one"
LOGIN_PATH = "/services/dain/login"
OBJECTS_PATH = "/services/durin/my/objects"

CONF_LOGIN = "login"
CONF_PASSWORD = "password"

# Temps de course par defaut (secondes) pour estimer la position.
DEFAULT_TRAVEL_TIME = 20

# Cle d'options : dict {object_id: {"open": secondes, "close": secondes}}
CONF_TRAVEL_TIMES = "travel_times"

# Le token JWT expire ~6h apres login : on le rafraichit avec une marge.
TOKEN_REFRESH_MARGIN = 600  # secondes avant expiration reelle

# Type d'objet correspondant a un volet roulant Profalux.
SHUTTER_TYPE = "Rolling_Shutter_Profalux"

PLATFORMS = ["cover"]
